"""Chat streaming orchestration (Slice C + D): reserve -> provider stream -> settle/release.

Financial lifecycle follows ADR-039 decision matrix and OQ-030/D-07. No DB transaction
is held open during provider streaming. All short DB operations use their own session
and commit; the reservation terminal transition is guarded by the existing DB trigger
so a reservation can never be both settled and released.
"""

import asyncio
import hashlib
import json
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import SessionFactory
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.repositories import conversations as conv_repo
from app.repositories import reservations as reservations_repo
from app.schemas.conversation import ChatStreamRequest
from app.services.llm import ChatRequest, LLMProvider, get_llm_provider
from app.services.reservation import FinanceService

logger = logging.getLogger(__name__)

REQUEST_NOT_FOUND = AppError("conversation_not_found", 404, "گفتگو یافت نشد.")
MODEL_UNAVAILABLE = AppError("llm_not_configured", 503, "provider مدل پیکربندی نشده است.")
INSUFFICIENT = AppError("insufficient_credit", 409, "اعتبار کافی موجود نیست.")

EVENT_ACK = "ack"
EVENT_ASSISTANT_CREATED = "assistant_created"
EVENT_DELTA = "delta"
EVENT_DONE = "done"
EVENT_ERROR = "error"
EVENT_CANCELLED = "cancelled"

_PERSIST_EVERY = 25
_CLEANUP_TIMEOUT_SECONDS = 15.0
_CLEANUP_CANCEL_GRACE_SECONDS = 3.0
PULSE_INTERVAL_SECONDS = 10.0
LEASE_EXPIRY_SECONDS = 60.0


def _outer_cancelled() -> bool:
    """تشخیص لغو خارجی Task (نه لغوی داخلی cleanup)."""
    task = asyncio.current_task()
    if task is None:
        return False
    cancelling = getattr(task, "cancelling", None)
    if callable(cancelling):
        return int(cancelling()) > 0
    return False


def _consume_cleanup_result(cleanup_task: asyncio.Task[object]) -> None:
    """دریافت نتیجه/exception cleanup در صورت پایان؛ بدون بلعیدن صامت."""
    try:
        cleanup_task.result()
    except asyncio.CancelledError:
        logger.warning("chat_terminal_cleanup_cancelled")
    except BaseException:
        logger.exception("chat_terminal_cleanup_exception")


async def _bounded_cleanup_wait(
    cleanup_task: asyncio.Task[object],
    phase1_timeout: float,
    phase2_grace: float,
) -> bool:
    """انتظار سه-فازی با deadlineهای مطلق و مستقل؛ True اگر لغو خارجی رخ داده باشد.

    مرحله ۱ (تا `phase1_timeout` ثانیه): صبر برای تکمیل cleanup با تحمل لغو خارجی؛
        لغو خارجی **هرگز** cleanup را cancel نمی‌کند (حفاظت shield).
    مرحله ۲ (فقط پس از انقضای واقعی مهلت ۱): `cleanup_task.cancel()` + حداکثر
        `phase2_grace` ثانیه فرصت اضافی (deadline مستقل).
    مرحله ۳: اگر هنوز pending بود، reference قوی در `SHUTDOWN_STATE.pending_cleanups`
        ثبت می‌شود و خطای بحرانی با شناسهٔ همبستگی لاگ می‌شود؛ DB disposal مسدود می‌ماند.

    هیچ await نامحدودی در مسیر نیست؛ deadlineها بر پایه `loop.time()` محاسبه می‌شوند.
    """
    from app.core.shutdown import SHUTDOWN_STATE

    loop = asyncio.get_running_loop()
    cancelled = False

    # ---- Phase 1: tolerate outer cancellations; never cancel cleanup here ----
    deadline1 = loop.time() + phase1_timeout
    while True:
        if cleanup_task.done():
            break
        remaining = deadline1 - loop.time()
        if remaining <= 0:
            break
        try:
            await asyncio.wait({cleanup_task}, timeout=remaining)
        except asyncio.CancelledError:
            cancelled = cancelled or _outer_cancelled()
            # ادامه انتظار روی هم‌ان cleanup؛ بدون cancel
    if cleanup_task.done():
        _consume_cleanup_result(cleanup_task)
        return cancelled

    # ---- Phase 2: only now (deadline genuinely expired) request cancellation ----
    cleanup_task.cancel()
    deadline2 = loop.time() + phase2_grace
    while True:
        if cleanup_task.done():
            break
        remaining = deadline2 - loop.time()
        if remaining <= 0:
            break
        try:
            await asyncio.wait({cleanup_task}, timeout=remaining)
        except asyncio.CancelledError:
            cancelled = cancelled or _outer_cancelled()
    if cleanup_task.done():
        _consume_cleanup_result(cleanup_task)
        return cancelled

    # ---- Phase 3: pending -> strong reference registry + fail-closed ----
    SHUTDOWN_STATE.pending_cleanups.add(cleanup_task)
    logger.critical(
        "chat_terminal_cleanup_pending",
        extra={"cleanup_task": repr(cleanup_task)},
    )
    return cancelled


class ChatStreamService:
    """ارکستراسیون چت استریم امن مالی."""

    def __init__(
        self,
        provider: LLMProvider | None = None,
        session_factory: Callable[[], AsyncSession] | None = None,
        on_financial: Callable[[str], None] | None = None,
    ) -> None:
        self._settings = get_settings()
        self._provider_override = provider
        self._session_factory = session_factory or SessionFactory
        self._on_financial = on_financial

    # ------------------------------------------------------------- helpers

    @staticmethod
    def _fingerprint(content: str, model: str | None) -> str:
        canonical = json.dumps({"content": content, "model": model}, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _get_provider(self) -> LLMProvider:
        if self._provider_override is not None:
            return self._provider_override
        provider = get_llm_provider()
        if provider is None:
            raise MODEL_UNAVAILABLE
        return provider

    @staticmethod
    def _sse(seq: int, event: str, payload: dict[str, Any]) -> str:
        return f"id:{seq}\nevent:{event}\ndata:{json.dumps(payload, ensure_ascii=False)}\n\n"

    async def _resolve_conversation(self, conversation_id: uuid.UUID | None, user_id: uuid.UUID) -> Conversation:
        if conversation_id is None:
            async with self._session_factory() as session:
                new_conv = await conv_repo.create_conversation(session, user_id=user_id)
                await session.commit()
                return new_conv
        async with self._session_factory() as session:
            existing_conv = await conv_repo.get_owned(session, conversation_id, user_id)
        if existing_conv is None:
            raise REQUEST_NOT_FOUND
        return existing_conv

    async def _reserve(self, user_id: uuid.UUID, key: str, fingerprint: str) -> Any:
        async with self._session_factory() as session:
            try:
                reservation = await FinanceService(session).reserve_credit(
                    user_id,
                    1,
                    idempotency_key=key,
                    payload_fingerprint=fingerprint,
                    request_id=None,
                )
                await session.commit()
                return reservation
            except AppError as exc:
                await session.rollback()
                if exc.code == "insufficient_credit":
                    raise INSUFFICIENT from exc
                raise

    async def _create_messages(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID, content: str, client_request_id: str, reservation_id: uuid.UUID
    ) -> tuple[uuid.UUID, uuid.UUID]:
        async with self._session_factory() as session:
            user_msg = await conv_repo.create_message_idempotent(
                session,
                conversation_id=conversation_id,
                user_id=user_id,
                role="user",
                content=content,
                client_request_id=client_request_id,
            )
            try:
                async with session.begin_nested():
                    assistant = await conv_repo.create_message(
                        session,
                        conversation_id=conversation_id,
                        user_id=user_id,
                        role="assistant",
                        status="streaming",
                        reservation_id=reservation_id,
                    )
            except Exception:
                # concurrent duplicate: someone else already created the assistant for this reservation
                existing = await conv_repo.get_message_by_reservation(session, reservation_id)
                if existing is not None:
                    await session.rollback()
                    return user_msg.id, existing.id
                raise
            await session.commit()
            return user_msg.id, assistant.id

    async def _load_assistant(self, reservation_id: uuid.UUID) -> Message | None:
        async with self._session_factory() as session:
            return await conv_repo.get_message_by_reservation(session, reservation_id)

    async def _persist_content(self, message_id: uuid.UUID, content: str, owner_token: str) -> bool:
        """ذخیرهٔ محتوای جزئی؛ فقط با مالکیت معتبر و وضعیت streaming (fencing)."""
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    update(Message).where(
                        Message.id == message_id,
                        Message.status == "streaming",
                        Message.stream_owner_token == owner_token,
                    ).values(content=content).returning(Message.id)
                )
            ).first()
            await session.commit()
            return row is not None

    async def _assert_stream_owned(self, message_id: uuid.UUID, owner_token: str) -> bool:
        """سازگاری مالکیت در لحظهٔ انتشار Delta (linearization point).

        اگر Recovery مالکیت را باطل کرده باشد (owner=NULL / stream_terminated)، این بررسی
        false برمی‌گرداند و Stream قدیمی باید بدون fallback abort شود.
        """
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(Message.id).where(
                        Message.id == message_id,
                        Message.status == "streaming",
                        Message.stream_owner_token == owner_token,
                    ).limit(1)
                )
            ).first()
            return row is not None

    async def _mark_billable_durable(self, message_id: uuid.UUID, owner_token: str) -> bool:
        """ثبت پایدار نشانگر billable پیش از انتشار نخستین Delta.

        اگر مالکیت از دست رفته باشد (recovery قبلاً ادعا کرده)، این درخواست باید no-op شود.
        """
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    update(Message).where(
                        Message.id == message_id,
                        Message.status == "streaming",
                        Message.stream_owner_token == owner_token,
                        Message.billable_output_seen.is_(False),
                    ).values(billable_output_seen=True).returning(Message.id)
                )
            ).first()
            await session.commit()
            return row is not None

    async def _finalize(
        self, reservation_id: uuid.UUID, billable: bool
    ) -> tuple[bool, str]:
        """اتمیک terminal.

        - اگر خروجی قابل‌صورتحساب (billable) تولید شده باشد، ابتدا settle تلاش می‌شود
          (طبق ADR-039؛ بعد از مهلت توسط FinanceService.settle رد می‌شود و به release
          امن بازمی‌گردد تا دوبار صورتحساب نشود).
        -         اگر خروجی قابل‌صورتحساب نباشد، مستقیماً release رخ می‌دهد.
        فقط یک گذار ترمینال ممکن است (گارد trigger دیتابیس).
        """
        if not billable:
            return await self._release_if_pending(reservation_id)

        s1 = self._session_factory()
        try:
            await FinanceService(s1).settle(reservation_id)
            await s1.commit()
            self._emit_financial("settled")
            return True, "settled"
        except AppError:
            await s1.rollback()
        finally:
            await s1.close()
        return await self._release_if_pending(reservation_id)

    def _emit_financial(self, outcome: str) -> None:
        if self._on_financial is not None:
            self._on_financial(outcome)

    async def _release_if_pending(self, reservation_id: uuid.UUID) -> tuple[bool, str]:
        s2 = self._session_factory()
        try:
            reservation = await reservations_repo.get_by_id(s2, reservation_id)
            if reservation is not None and reservation.status == "pending":
                await FinanceService(s2).release(reservation_id, reason="chat_terminal_release")
                await s2.commit()
                self._emit_financial("released")
                return False, "released"
            return False, "already_terminal"
        finally:
            await s2.close()

    async def _heartbeat_loop(self, message_id: uuid.UUID, owner_token: str) -> None:
        """ضربان پایدار Stream؛ مستقل از تولید Token؛ فقط با مالکیت و وضعیت streaming."""
        while True:
            await asyncio.sleep(PULSE_INTERVAL_SECONDS)
            try:
                async with self._session_factory() as session:
                    await session.execute(
                        update(Message).where(
                            Message.id == message_id,
                            Message.status == "streaming",
                            Message.stream_owner_token == owner_token,
                        ).values(heartbeat_at=datetime.now(UTC))
                    )
                    await session.commit()
            except Exception:  # noqa: BLE001
                logger.debug("heartbeat_failed")

    async def _finalize_atomic(
        self,
        reservation_id: uuid.UUID,
        billable: bool,
        assistant_id: uuid.UUID,
        terminal_status: str,
        content: str,
        owner_token: str | None = None,
    ) -> tuple[bool, str]:
        """نهایی‌سازی مالی + پیام در یک تراکنش PostgreSQL (بدون شکاف Crash).

        - بدون billable → release؛ با billable → settle (با حفظ deadline/late-completion).
        - اگر settle به‌علت مهلت رد شود، rollback صافی (savepoint) و مسیر release امن.
        - وضعیت Message در همان تراکنش به وضعیت نهایی معتبر منتقل می‌شود.
        - متریک مالی فقط پس از commit در caller emit می‌شود.
        """
        session = self._session_factory()
        try:
            finance = FinanceService(session)
            settled = False
            if billable:
                try:
                    async with session.begin_nested():
                        await finance.settle(reservation_id)
                    settled = True
                except AppError:
                    # مهلت/late-completion (D-07/OQ-030): rollback nested + fallback release
                    pass
            if not settled:
                await finance.release(reservation_id, reason="chat_terminal_release")
            # وضعیت نهایی پیام در همان تراکنش؛ فقط از حالت streaming قابل تغییر است (fencing).
            if settled:
                msg_status = terminal_status
            else:
                msg_status = terminal_status if terminal_status in ("failed", "partial") else "cancelled"
            values: dict[str, object] = {
                "status": msg_status,
                "content": content,
                "billable_output_seen": billable,
                "stream_terminated": True,
            }
            if settled:
                values["settled_at"] = datetime.now(UTC)
            # Fencing: فقط با مالکیت معتبر و وضعیت streaming قابل تغییر است.
            message_where = [Message.id == assistant_id, Message.status == "streaming"]
            if owner_token is not None:
                message_where.append(Message.stream_owner_token == owner_token)
            claimed_msg = (
                await session.execute(update(Message).where(*message_where).values(**values).returning(Message.id))
            ).first()
            if claimed_msg is None:
                # مالکیت از دست رفته (recovery پیشتر ادعا کرده)؛ از تعهد مالی ناقص جلوگیری کن.
                await session.rollback()
                return False, "lost_ownership"
            await session.commit()
            return settled, ("settled" if settled else "released")
        except BaseException:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def _run_terminal_cleanup(
        self,
        reservation_id: uuid.UUID,
        billable: bool,
        assistant_id: uuid.UUID,
        terminal_status: str,
        content: str,
        owner_token: str | None = None,
    ) -> None:
        """نهایی‌سازی مالی + وضعیت پیام به‌صورت اتمیک (ایمن در برابر لغو).

        متریک مالی فقط پس از commit موفق تراکنش emit می‌شود.
        """
        try:
            settled, outcome = await self._finalize_atomic(
                reservation_id, billable, assistant_id, terminal_status, content, owner_token
            )
            if outcome != "lost_ownership":
                self._emit_financial(outcome)
        except Exception:  # noqa: BLE001 - never report uncommitted outcome as success
            logger.exception("chat_terminal_finalize_failed")

    async def _record_terminal(
        self, message_id: uuid.UUID, status: str, content: str, settled: bool
    ) -> None:
        async with self._session_factory() as session:
            values: dict[str, object] = {"status": status, "content": content}
            if settled:
                values["settled_at"] = datetime.now(UTC)
            await session.execute(update(Message).where(Message.id == message_id).values(**values))
            await session.commit()

    # ------------------------------------------------------------- preflight (pre-stream validation)

    async def preflight(self, req: ChatStreamRequest, user: User) -> None:
        """اعتبارسنجیِ قبل از شروع stream (برای بازگرداندن خطای JSON مناسب).

        مالکیت گفتگو و تعارض idempotency (همان کلید با بار متفاوت) باید پیش از
        شروع StreamingResponse بررسی شوند تا خطاها به‌جای قطعِ پس از 200، به‌صورت
        پاسخ استاندارد (404/409) بازگردند.
        """
        await self._resolve_conversation(req.conversation_id, user.id)
        fp = self._fingerprint(req.content, req.model)
        key = f"chat:{user.id}:{req.client_request_id}"
        from app.services.reservation import IDEMPOTENCY_CONFLICT

        async with self._session_factory() as session:
            existing = await reservations_repo.get_by_idempotency_key(session, user.id, key)
        if existing is not None and existing.payload_fingerprint != fp:
            raise IDEMPOTENCY_CONFLICT

    # ------------------------------------------------------------- main stream

    async def stream_chat(self, req: ChatStreamRequest, user: User, last_event_id: str | None = None) -> AsyncIterator[str]:
        conv = await self._resolve_conversation(req.conversation_id, user.id)
        fp = self._fingerprint(req.content, req.model)
        key = f"chat:{user.id}:{req.client_request_id}"
        reservation = await self._reserve(user.id, key, fp)
        # reserve amount is 1; guard duplicate reservation fingerprint
        assistant = await self._load_assistant(reservation.id)
        if assistant is not None:
            async for ev in self._replay(assistant, conv.id):
                yield ev
            return
        user_msg_id, assistant_id = await self._create_messages(conv.id, user.id, req.content, req.client_request_id, reservation.id)
        # مالکیت Stream + heartbeat اولیه (fencing برای recovery)
        owner_token = str(uuid.uuid4())
        async with self._session_factory() as session:
            await session.execute(
                update(Message).where(Message.id == assistant_id).values(
                    stream_owner_token=owner_token, heartbeat_at=datetime.now(UTC)
                )
            )
            await session.commit()
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(assistant_id, owner_token))

        request_id = str(uuid.uuid4())
        seq = 0
        seq += 1
        yield self._sse(seq, EVENT_ACK, {"request_id": request_id, "conversation_id": str(conv.id), "message_id": str(assistant_id)})
        seq += 1
        yield self._sse(seq, EVENT_ASSISTANT_CREATED, {"message_id": str(assistant_id), "sequence": seq})

        provider = self._get_provider()
        billable = False
        parts: list[str] = []
        terminal_status = "completed"
        terminal_error: str | None = None
        finalized = False
        lost_ownership = False

        try:
            attempts = 0
            while True:
                emitted = False
                err: str | None = None
                try:
                    async for chunk in provider.stream_chat(
                        ChatRequest(messages=[{"role": "user", "content": req.content}])
                    ):
                        if chunk.error:
                            err = chunk.error
                            break
                        if chunk.done:
                            break
                        if chunk.delta:
                            # قبل از هر Delta billable، مالکیت دوباره بررسی می‌شود (fencing هر Delta)
                            if not await self._assert_stream_owned(assistant_id, owner_token):
                                lost_ownership = True
                                break
                            if not billable:
                                # ثبت پایدار billable پیش از انتشار نخستین Delta (fencing)
                                if not await self._mark_billable_durable(assistant_id, owner_token):
                                    lost_ownership = True
                                    break
                            emitted = True
                            billable = True
                            parts.append(chunk.delta)
                            seq += 1
                            yield self._sse(seq, EVENT_DELTA, {"sequence": seq, "content": chunk.delta})
                            if len(parts) % _PERSIST_EVERY == 0:
                                await self._persist_content(assistant_id, "".join(parts), owner_token)
                        if lost_ownership:
                            break
                except asyncio.CancelledError:
                    # وضعیت terminal دقیق بر اساس ADR-039:
                    # بدون خروجی billable -> cancelled؛ با خروجی billable -> partial (settle).
                    terminal_status = "partial" if billable else "cancelled"
                    raise
                if lost_ownership:
                    terminal_status = "cancelled"
                    break
                if not emitted and err is None:
                    break
                if not emitted and err is not None:
                    if attempts >= self._settings.llm_max_retries:
                        terminal_status = "failed"
                        terminal_error = err
                        break
                    attempts += 1
                    continue
                # emitted content
                if err is not None:
                    terminal_status = "partial"
                    terminal_error = err
                break
        finally:
            if not heartbeat_task.done():
                heartbeat_task.cancel()
                await asyncio.gather(heartbeat_task, return_exceptions=True)
            if not finalized:
                finalized = True
                content = "".join(parts)
                # سیاست زمانی صریح دو-فازی (deadlineهای مستقل):
                #   مرحله ۱: تا _CLEANUP_TIMEOUT_SECONDS (۱۵s) برای cleanup عادی.
                #   مرحله ۲: اگر هنوز تمام نشده، cancel + حداکثر _CLEANUP_CANCEL_GRACE_SECONDS (۳s)
                #             فرصت اضافی (deadline مستقل؛ از deadline منقضی‌شدهٔ مرحله ۱ استفاده نمی‌شود).
                # خود task نیز hard-bounded است (wait_for داخلی ۱۵s) تا هیچ Task دارای DB access
                # پس از dispose نماند و همه انتظارها کران‌دار باشند.
                cleanup_task = asyncio.create_task(
                    asyncio.wait_for(
                        self._run_terminal_cleanup(
                            reservation.id, billable, assistant_id, terminal_status, content, owner_token
                        ),
                        timeout=_CLEANUP_TIMEOUT_SECONDS,
                    )
                )
                cancelled = await _bounded_cleanup_wait(
                    cleanup_task,
                    _CLEANUP_TIMEOUT_SECONDS,
                    _CLEANUP_CANCEL_GRACE_SECONDS,
                )
                if cancelled:
                    raise asyncio.CancelledError

        if terminal_error is not None:
            seq += 1
            yield self._sse(seq, EVENT_ERROR, {"sequence": seq, "code": terminal_status, "message": terminal_error})
        seq += 1
        yield self._sse(seq, EVENT_DONE, {"sequence": seq, "status": terminal_status, "content": "".join(parts)})

    async def _replay(self, assistant: Message, conversation_id: uuid.UUID) -> AsyncIterator[str]:
        """بازسازی قطعی پاسخ از state پایدار؛ بدون فراخوانی دوبارهٔ provider/رزرو/settle."""
        seq = 0
        seq += 1
        yield self._sse(seq, EVENT_ACK, {"request_id": str(assistant.id), "conversation_id": str(conversation_id), "message_id": str(assistant.id)})
        seq += 1
        yield self._sse(seq, EVENT_ASSISTANT_CREATED, {"message_id": str(assistant.id), "sequence": seq})
        seq += 1
        yield self._sse(seq, EVENT_DELTA, {"sequence": seq, "content": assistant.content})
        seq += 1
        yield self._sse(seq, EVENT_DONE, {"sequence": seq, "status": assistant.status, "content": assistant.content})
