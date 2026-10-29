"""تست‌های یکپارچهٔ هستهٔ مالی (Slice A) روی PostgreSQL واقعی (ADR-035)."""

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import get_settings
from app.core.errors import AppError
from app.repositories import credit_accounts as accounts_repo
from app.repositories import credit_ledger as ledger_repo
from app.repositories import reservations as reservations_repo
from app.repositories import users as users_repo
from app.services.reservation import FinanceService
from sqlalchemy import exc as sqlalchemy_exc
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.skipif(
    os.environ.get("DARSYAR_TEST_DB") != "1",
    reason="requires real PostgreSQL schema prepared by make test-db",
)

TEST_ENGINE = create_async_engine(get_settings().database_url, poolclass=NullPool)
TEST_SESSION_FACTORY = async_sessionmaker(TEST_ENGINE, expire_on_commit=False)


def _new_phone() -> str:
    return f"+989{str(uuid.uuid4().int)[:9]}"


async def _make_user_with_balance(balance: int) -> tuple[uuid.UUID, str]:
    phone = _new_phone()
    async with TEST_SESSION_FACTORY() as session:
        user = await users_repo.create(session, phone=phone, role="user")
        await accounts_repo.create(session, user_id=user.id, available_balance=balance)
        await session.commit()
        return user.id, phone


@pytest.fixture()
async def user_with_balance() -> tuple[uuid.UUID, str]:
    yield await _make_user_with_balance(100)


async def _bal(session, user_id: uuid.UUID) -> int | None:
    acc = await accounts_repo.get_for_update(session, user_id) if await accounts_repo.exists(session, user_id) else None
    return acc.available_balance if acc else None


@pytest.mark.asyncio
async def test_reserve_decreases_balance_exactly_once(user_with_balance) -> None:
    user_id, _ = user_with_balance
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        await service.reserve_credit(user_id, 10, idempotency_key="k1", payload_fingerprint="f1")
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        assert await _bal(session, user_id) == 90
        total = await ledger_repo.sum_balance_affecting(session, user_id)
        assert total == -10


@pytest.mark.asyncio
async def test_insufficient_balance_no_reservation_no_debit(user_with_balance) -> None:
    user_id, _ = user_with_balance
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        with pytest.raises(AppError) as excinfo:
            await service.reserve_credit(user_id, 999, idempotency_key="k2", payload_fingerprint="f2")
        assert excinfo.value.code == "insufficient_credit"
        await session.rollback()
    async with TEST_SESSION_FACTORY() as session:
        assert await _bal(session, user_id) == 100
        rows = await session.execute(text("SELECT count(*) FROM reservations WHERE user_id = :u"), {"u": str(user_id)})
        assert rows.scalar_one() == 0
        events = await session.execute(text("SELECT count(*) FROM credit_ledger WHERE user_id = :u"), {"u": str(user_id)})
        assert events.scalar_one() == 0


@pytest.mark.asyncio
async def test_duplicate_key_same_payload_no_duplicate(user_with_balance) -> None:
    user_id, _ = user_with_balance
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        first = await service.reserve_credit(user_id, 10, idempotency_key="k3", payload_fingerprint="f3")
        second = await service.reserve_credit(user_id, 10, idempotency_key="k3", payload_fingerprint="f3")
        await session.commit()
        assert first.id == second.id
    async with TEST_SESSION_FACTORY() as session:
        assert await _bal(session, user_id) == 90
        events = await session.execute(text("SELECT count(*) FROM credit_ledger WHERE user_id = :u"), {"u": str(user_id)})
        assert events.scalar_one() == 1


@pytest.mark.asyncio
async def test_same_key_different_payload_conflict_no_effect(user_with_balance) -> None:
    user_id, _ = user_with_balance
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        await service.reserve_credit(user_id, 10, idempotency_key="k4", payload_fingerprint="f4")
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        with pytest.raises(AppError) as excinfo:
            await service.reserve_credit(user_id, 10, idempotency_key="k4", payload_fingerprint="DIFFERENT")
        assert excinfo.value.code == "idempotency_conflict"
        await session.rollback()
    async with TEST_SESSION_FACTORY() as session:
        assert await _bal(session, user_id) == 90
        events = await session.execute(text("SELECT count(*) FROM credit_ledger WHERE user_id = :u"), {"u": str(user_id)})
        assert events.scalar_one() == 1


@pytest.mark.asyncio
async def test_settlement_does_not_debit_twice(user_with_balance) -> None:
    user_id, _ = user_with_balance
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        reservation = await service.reserve_credit(user_id, 20, idempotency_key="k5", payload_fingerprint="f5")
        await session.commit()
        reservation_id = reservation.id
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        settled = await service.settle(reservation_id)
        await session.commit()
        assert settled.status == "settled"
    async with TEST_SESSION_FACTORY() as session:
        assert await _bal(session, user_id) == 80
        events = await session.execute(text("SELECT count(*) FROM credit_ledger WHERE user_id = :u"), {"u": str(user_id)})
        assert events.scalar_one() == 1
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        again = await service.settle(reservation_id)
        await session.commit()
        assert again.status == "settled"
    async with TEST_SESSION_FACTORY() as session:
        assert await _bal(session, user_id) == 80
        events = await session.execute(text("SELECT count(*) FROM credit_ledger WHERE user_id = :u"), {"u": str(user_id)})
        assert events.scalar_one() == 1


@pytest.mark.asyncio
async def test_release_restores_balance_once_and_repeat_is_noop(user_with_balance) -> None:
    user_id, _ = user_with_balance
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        reservation = await service.reserve_credit(user_id, 30, idempotency_key="k6", payload_fingerprint="f6")
        await session.commit()
        reservation_id = reservation.id
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        released = await service.release(reservation_id)
        await session.commit()
        assert released.status == "released"
    async with TEST_SESSION_FACTORY() as session:
        assert await _bal(session, user_id) == 100
        events = await session.execute(text("SELECT count(*) FROM credit_ledger WHERE user_id = :u"), {"u": str(user_id)})
        assert events.scalar_one() == 2  # spend + refund
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        again = await service.release(reservation_id)
        await session.commit()
        assert again.status == "released"
    async with TEST_SESSION_FACTORY() as session:
        assert await _bal(session, user_id) == 100
        events = await session.execute(text("SELECT count(*) FROM credit_ledger WHERE user_id = :u"), {"u": str(user_id)})
        assert events.scalar_one() == 2


@pytest.mark.asyncio
async def test_race_settle_vs_release_only_one_terminal(user_with_balance) -> None:
    user_id, _ = user_with_balance
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        reservation = await service.reserve_credit(user_id, 10, idempotency_key="k7", payload_fingerprint="f7")
        await session.commit()
        reservation_id = reservation.id

    outcomes: list[str] = []

    async def attempt(target: str) -> None:
        async with TEST_SESSION_FACTORY() as session:
            service = FinanceService(session)
            try:
                if target == "settled":
                    await service.settle(reservation_id)
                else:
                    await service.release(reservation_id)
                await session.commit()
                outcomes.append(target)
            except AppError as exc:
                outcomes.append(exc.code)

    await asyncio.gather(attempt("settled"), attempt("released"))
    # هر دو «موفق» تلقی شوند، یکی باید no-op باشد؛ وضعیت نهایی یکی از دو حالت ترمینال است.
    assert set(outcomes) <= {"settled", "released", "invalid_reservation_state"}
    async with TEST_SESSION_FACTORY() as session:
        final = await reservations_repo.get_by_id(session, reservation_id)
        assert final.status in ("settled", "released")
        if final.status == "released":
            assert await _bal(session, user_id) == 100
        else:
            assert await _bal(session, user_id) == 90


@pytest.mark.asyncio
async def test_parallel_reservations_cannot_overspend(user_with_balance) -> None:
    user_id, _ = user_with_balance
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        await service.reserve_credit(user_id, 60, idempotency_key="k8a", payload_fingerprint="f8a")
        await session.commit()

    async def try_reserve(key: str) -> str:
        async with TEST_SESSION_FACTORY() as session:
            service = FinanceService(session)
            try:
                await service.reserve_credit(user_id, 60, idempotency_key=key, payload_fingerprint="f8b")
                await session.commit()
                return "ok"
            except AppError as exc:
                await session.rollback()
                return exc.code

    outcomes = await asyncio.gather(try_reserve("k8b"), try_reserve("k8c"))
    assert outcomes.count("ok") <= 1
    async with TEST_SESSION_FACTORY() as session:
        balance = await _bal(session, user_id)
        assert balance is not None and balance >= 0
        reservations = await session.execute(
            text("SELECT count(*) FROM reservations WHERE user_id = :u AND status = 'pending'"), {"u": str(user_id)}
        )
        assert reservations.scalar_one() <= 1


@pytest.mark.asyncio
async def test_ledger_entries_cannot_be_updated_or_deleted(user_with_balance) -> None:
    user_id, _ = user_with_balance
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        await service.reserve_credit(user_id, 10, idempotency_key="k9", payload_fingerprint="f9")
        await session.commit()
    # مسیر مجاز اپلیکیشن فقط درج است؛ هیچ تابع update/delete در repository وجود ندارد.
    import inspect

    from app.repositories import credit_ledger as ledger_module

    defined_fns = {
        name
        for name, obj in inspect.getmembers(ledger_module)
        if inspect.isfunction(obj) and obj.__module__ == ledger_module.__name__
    }
    assert defined_fns == {"create", "sum_balance_affecting"}
    # به‌روزرسانی غیرمجاز مستقیم توسط trigger تغییرناپذیری DB رد می‌شود.
    async with TEST_SESSION_FACTORY() as session:
        with pytest.raises(sqlalchemy_exc.SQLAlchemyError) as excinfo:
            await session.execute(text("UPDATE credit_ledger SET amount = 0 WHERE user_id = :u"), {"u": str(user_id)})
        assert "credit_ledger_immutable" in str(excinfo.value)
        await session.rollback()


@pytest.mark.asyncio
async def test_terminal_transition_blocked_by_db_trigger(user_with_balance) -> None:
    user_id, _ = user_with_balance
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        reservation = await service.reserve_credit(user_id, 10, idempotency_key="k10", payload_fingerprint="f10")
        await session.commit()
        reservation_id = reservation.id
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        await service.settle(reservation_id)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        with pytest.raises(Exception) as excinfo:
            await session.execute(
                text("UPDATE reservations SET status = 'released', released_at = now() WHERE id = :r"),
                {"r": str(reservation_id)},
            )
            await session.commit()
        assert "reservation_terminal_transition_blocked" in str(excinfo.value)
        await session.rollback()


@pytest.mark.asyncio
async def test_unlimited_reservation_does_not_change_balance(user_with_balance) -> None:
    user_id, _ = user_with_balance
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        reservation = await service.reserve_unlimited(user_id, idempotency_key="k11", payload_fingerprint="f11")
        await session.commit()
        reservation_id = reservation.id
    async with TEST_SESSION_FACTORY() as session:
        assert await _bal(session, user_id) == 100
        events = await session.execute(text("SELECT count(*) FROM credit_ledger WHERE user_id = :u"), {"u": str(user_id)})
        assert events.scalar_one() == 0
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        await service.settle(reservation_id)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        assert await _bal(session, user_id) == 100


@pytest.mark.asyncio
async def test_reconcile_releases_stale_pending_safely(user_with_balance) -> None:
    user_id, _ = user_with_balance
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        reservation = await service.reserve_credit(user_id, 10, idempotency_key="k12", payload_fingerprint="f12")
        await session.commit()
        reservation_id = reservation.id
    async with TEST_SESSION_FACTORY() as session:
        result = await session.execute(text("UPDATE reservations SET created_at = :t WHERE id = :r"), {
            "t": datetime.now(UTC) - timedelta(days=1),
            "r": str(reservation_id),
        })
        await session.commit()
        assert result.rowcount == 1
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        released = await service.reconcile_stale(batch_limit=10, user_id=user_id)
        await session.commit()
        assert released == 1
    async with TEST_SESSION_FACTORY() as session:
        assert await _bal(session, user_id) == 100
        final = await reservations_repo.get_by_id(session, reservation_id)
        assert final.status == "released"
        events = await session.execute(text("SELECT count(*) FROM credit_ledger WHERE user_id = :u"), {"u": str(user_id)})
        assert events.scalar_one() == 2
    # reconcile دوم نباید refund تکراری بسازد.
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        second = await service.reconcile_stale(batch_limit=10, user_id=user_id)
        await session.commit()
        assert second == 0
    async with TEST_SESSION_FACTORY() as session:
        events = await session.execute(text("SELECT count(*) FROM credit_ledger WHERE user_id = :u"), {"u": str(user_id)})
        assert events.scalar_one() == 2


@pytest.mark.asyncio
async def test_reconcile_skips_settled_reservations(user_with_balance) -> None:
    user_id, _ = user_with_balance
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        reservation = await service.reserve_credit(user_id, 10, idempotency_key="k13", payload_fingerprint="f13")
        await session.commit()
        reservation_id = reservation.id
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        await service.settle(reservation_id)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        result = await session.execute(text("UPDATE reservations SET created_at = :t WHERE id = :r"), {
            "t": datetime.now(UTC) - timedelta(days=1),
            "r": str(reservation_id),
        })
        await session.commit()
        assert result.rowcount == 1
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        released = await service.reconcile_stale(batch_limit=10, user_id=user_id)
        await session.commit()
        assert released == 0
    async with TEST_SESSION_FACTORY() as session:
        assert await _bal(session, user_id) == 90
        final = await reservations_repo.get_by_id(session, reservation_id)
        assert final.status == "settled"


@pytest.mark.asyncio
async def test_ledger_direct_update_delete_rejected_by_db_trigger_but_insert_allowed(user_with_balance) -> None:
    user_id, _ = user_with_balance
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        await service.reserve_credit(user_id, 10, idempotency_key="k20", payload_fingerprint="f20")
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        with pytest.raises(sqlalchemy_exc.SQLAlchemyError) as excinfo:
            await session.execute(text("UPDATE credit_ledger SET reason = 'hacked' WHERE user_id = :u"), {"u": str(user_id)})
        assert "credit_ledger_immutable" in str(excinfo.value)
        await session.rollback()
        with pytest.raises(sqlalchemy_exc.SQLAlchemyError) as excinfo:
            await session.execute(text("DELETE FROM credit_ledger WHERE user_id = :u"), {"u": str(user_id)})
        assert "credit_ledger_immutable" in str(excinfo.value)
        await session.rollback()
        # درج مستقیم همچنان مجاز است.
        result = await session.execute(
            text(
                "INSERT INTO credit_ledger (user_id, kind, amount, idempotency_key) "
                "VALUES (:u, 'adjust', 5, 'direct-insert-test')"
            ),
            {"u": str(user_id)},
        )
        assert result.rowcount == 1
        await session.rollback()


@pytest.mark.asyncio
async def test_ledger_projection_consistency_reserve_then_release(user_with_balance) -> None:
    user_id, _ = user_with_balance
    initial = 100
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        reservation = await service.reserve_credit(user_id, 25, idempotency_key="k21", payload_fingerprint="f21")
        await session.commit()
        reservation_id = reservation.id
    async with TEST_SESSION_FACTORY() as session:
        assert await _bal(session, user_id) == 75
        assert await ledger_repo.sum_balance_affecting(session, user_id) == -25
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        await service.release(reservation_id)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        assert await _bal(session, user_id) == initial
        assert await ledger_repo.sum_balance_affecting(session, user_id) == 0


@pytest.mark.asyncio
async def test_ledger_projection_consistency_settle_no_second_debit(user_with_balance) -> None:
    user_id, _ = user_with_balance
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        reservation = await service.reserve_credit(user_id, 25, idempotency_key="k22", payload_fingerprint="f22")
        await session.commit()
        reservation_id = reservation.id
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        await service.settle(reservation_id)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        assert await _bal(session, user_id) == 75
        assert await ledger_repo.sum_balance_affecting(session, user_id) == -25


@pytest.mark.asyncio
async def test_ledger_projection_consistency_unlimited_no_effect(user_with_balance) -> None:
    user_id, _ = user_with_balance
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        await service.reserve_unlimited(user_id, idempotency_key="k23", payload_fingerprint="f23")
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        assert await _bal(session, user_id) == 100
        assert await ledger_repo.sum_balance_affecting(session, user_id) == 0


@pytest.mark.asyncio
async def test_ledger_projection_consistency_rollback(user_with_balance) -> None:
    user_id, _ = user_with_balance
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        await service.reserve_credit(user_id, 40, idempotency_key="k24", payload_fingerprint="f24")
        await session.rollback()
    async with TEST_SESSION_FACTORY() as session:
        assert await _bal(session, user_id) == 100
        assert await ledger_repo.sum_balance_affecting(session, user_id) == 0


@pytest.mark.asyncio
async def test_reconcile_rejects_invalid_batch_limit(user_with_balance) -> None:
    user_id, _ = user_with_balance
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        for invalid in (0, -1, -100):
            with pytest.raises(AppError) as excinfo:
                await service.reconcile_stale(batch_limit=invalid)
            assert excinfo.value.code == "invalid_batch_limit"
        await session.rollback()


@pytest.mark.asyncio
async def test_reconcile_batch_limit_actually_limits_processed_reservations(user_with_balance) -> None:
    user_id, _ = user_with_balance
    keys = [f"k-batch-{i}" for i in range(5)]
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        for key in keys:
            await service.reserve_credit(user_id, 5, idempotency_key=key, payload_fingerprint="f-batch")
        await session.commit()
    # همهٔ ۵ رزرو را به یک سن کهنه منتقل می‌کنیم (ترتیب قطعی: created_at صعودی).
    async with TEST_SESSION_FACTORY() as session:
        await session.execute(
            text("UPDATE reservations SET created_at = :t WHERE user_id = :u"),
            {"t": datetime.now(UTC) - timedelta(days=1), "u": str(user_id)},
        )
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        first = await service.reconcile_stale(batch_limit=2, user_id=user_id)
        await session.commit()
        assert first == 2
    async with TEST_SESSION_FACTORY() as session:
        released = await session.execute(
            text("SELECT count(*) FROM reservations WHERE user_id = :u AND status = 'released'"),
            {"u": str(user_id)},
        )
        pending = await session.execute(
            text("SELECT count(*) FROM reservations WHERE user_id = :u AND status = 'pending'"),
            {"u": str(user_id)},
        )
        assert released.scalar_one() == 2
        assert pending.scalar_one() == 3
    # اجرای بعدی بقیهٔ رزروهای واجد شرایط را پردازش می‌کند.
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        second = await service.reconcile_stale(batch_limit=10, user_id=user_id)
        await session.commit()
        assert second == 3
    async with TEST_SESSION_FACTORY() as session:
        pending = await session.execute(
            text("SELECT count(*) FROM reservations WHERE user_id = :u AND status = 'pending'"),
            {"u": str(user_id)},
        )
        assert pending.scalar_one() == 0


@pytest.mark.asyncio
async def test_ledger_projection_consistency_equation_explicit(user_with_balance) -> None:
    """معادلهٔ صریح: available_balance == opening_balance + sum_balance_affecting."""
    user_id, _ = user_with_balance
    async with TEST_SESSION_FACTORY() as session:
        opening = await _bal(session, user_id)
        assert opening == 100
    # مورد settle: یک بدهی منفی در مجموع و projectionِ منطبق.
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        reservation = await service.reserve_credit(user_id, 30, idempotency_key="k-eq-1", payload_fingerprint="f-eq")
        await session.commit()
        reservation_id = reservation.id
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        await service.settle(reservation_id)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        balance = await _bal(session, user_id)
        total = await ledger_repo.sum_balance_affecting(session, user_id)
        assert balance == opening + total
    # مورد release: جبران کامل، مجموع صفر، projection به baseline برمی‌گردد.
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        reservation = await service.reserve_credit(user_id, 20, idempotency_key="k-eq-2", payload_fingerprint="f-eq")
        await session.commit()
        reservation_id = reservation.id
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        await service.release(reservation_id)
        await session.commit()
    async with TEST_SESSION_FACTORY() as session:
        balance = await _bal(session, user_id)
        total = await ledger_repo.sum_balance_affecting(session, user_id)
        assert balance == opening + total


@pytest.mark.asyncio
async def test_rollback_leaves_no_partial_mutation(user_with_balance) -> None:
    user_id, _ = user_with_balance
    async with TEST_SESSION_FACTORY() as session:
        service = FinanceService(session)
        with pytest.raises(RuntimeError):
            # شبیه‌سازی شکست پس از رزرو پیش از commit
            await service.reserve_credit(user_id, 10, idempotency_key="k14", payload_fingerprint="f14")
            raise RuntimeError("boom")
        await session.rollback()
    async with TEST_SESSION_FACTORY() as session:
        assert await _bal(session, user_id) == 100
        reservations = await session.execute(text("SELECT count(*) FROM reservations WHERE user_id = :u"), {"u": str(user_id)})
        assert reservations.scalar_one() == 0
        events = await session.execute(text("SELECT count(*) FROM credit_ledger WHERE user_id = :u"), {"u": str(user_id)})
        assert events.scalar_one() == 0
