"""تست‌های سخت‌سازی Deployment: امنیت Metrics و زمان‌بندی بازیابی worker."""

from types import SimpleNamespace

import pytest
from app.core.operations import _metrics_peer_allowed
from app.services.worker import WorkerSettings

DEFAULT_NETWORKS = ["127.0.0.1", "::1"]


def test_metrics_peer_loopback_allowed() -> None:
    assert _metrics_peer_allowed("127.0.0.1", DEFAULT_NETWORKS) is True
    assert _metrics_peer_allowed("::1", DEFAULT_NETWORKS) is True


def test_metrics_peer_external_rejected_even_with_header() -> None:
    # حتی اگر X-Forwarded-For (جعل‌شده) وجود داشته باشد، peer خارجی رد می‌شود.
    assert _metrics_peer_allowed("203.0.113.5", DEFAULT_NETWORKS) is False
    assert _metrics_peer_allowed(None, DEFAULT_NETWORKS) is False
    assert _metrics_peer_allowed("not-an-ip", DEFAULT_NETWORKS) is False


def test_metrics_peer_allowed_when_network_configured() -> None:
    assert _metrics_peer_allowed("172.18.3.7", ["127.0.0.1", "172.18.0.0/16"]) is True


@pytest.mark.asyncio
async def test_metrics_endpoint_rejects_external_peer() -> None:
    from app.core.operations import metrics

    internal = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), headers={})
    external = SimpleNamespace(client=SimpleNamespace(host="203.0.113.9"), headers={"x-forwarded-for": "10.0.0.1"})

    import json

    ok = await metrics(internal)
    assert ok.status_code == 200
    denied = await metrics(external)
    assert denied.status_code == 403
    assert json.loads(denied.body.decode("utf-8")) == {"detail": "forbidden"}


def test_worker_schedules_stale_release_cron() -> None:
    settings_cls = WorkerSettings
    names = {cj.name for cj in settings_cls.cron_jobs}
    assert names == {
        "release-stale-reservations",
        "expire-plan-entitlements",
        "recover-orphan-stream-messages",
    }
    assert all(cj.run_at_startup is True for cj in settings_cls.cron_jobs)


def test_draining_server_sets_draining_on_signal() -> None:
    from app.core.run_server import DrainingServer
    from app.core.shutdown import SHUTDOWN_STATE

    SHUTDOWN_STATE.draining = False
    server = DrainingServer.__new__(DrainingServer)  # بدون اجرای واقعی
    # مقادیر موردنیاز برای handle_exit
    server._captured_signals = []
    server.should_exit = False
    server.force_exit = False
    server.handle_exit(15, None)  # SIGTERM
    assert SHUTDOWN_STATE.draining is True
    assert server.should_exit is True
    SHUTDOWN_STATE.draining = False


@pytest.mark.asyncio
async def test_entitlement_expiry_cron_delegates_to_plan_service(monkeypatch) -> None:
    from app.services.plans import PlanService
    from app.services.worker import expire_plan_entitlements

    calls: dict[str, object] = {}

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def commit(self) -> None:
            calls["committed"] = True

    async def fake_expire(self, *, batch_limit: int = 200, user_id=None) -> int:
        calls["batch_limit"] = batch_limit
        return 3

    monkeypatch.setattr("app.db.session.SessionFactory", lambda: FakeSession())
    monkeypatch.setattr(PlanService, "expire_due_entitlements", fake_expire)

    assert await expire_plan_entitlements({"batch_limit": "7"}) == {"expired": 3}
    assert calls == {"batch_limit": 7, "committed": True}


@pytest.mark.asyncio
async def test_request_size_limit_rejects_declared_oversized_body(monkeypatch) -> None:
    import app.main as main_module
    from httpx import ASGITransport, AsyncClient

    monkeypatch.setattr(main_module.settings, "max_request_bytes", 32)
    async with AsyncClient(
        transport=ASGITransport(app=main_module.app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/health/live", content=b"x" * 64)

    assert response.status_code == 413
    assert response.json()["code"] == "payload_too_large"


def test_client_ip_accepts_forwarded_header_from_trusted_cidr(monkeypatch) -> None:
    from types import SimpleNamespace

    from app.api.deps import client_ip
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "forwarded_allow_ips", "127.0.0.1,172.18.0.0/16")
    request = SimpleNamespace(
        client=SimpleNamespace(host="172.18.3.7"),
        headers={"x-forwarded-for": "203.0.113.9, 10.0.0.1"},
    )
    assert client_ip(request) == "203.0.113.9"  # type: ignore[arg-type]


def test_client_ip_ignores_forwarded_header_from_untrusted_peer(monkeypatch) -> None:
    from types import SimpleNamespace

    from app.api.deps import client_ip
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "forwarded_allow_ips", "127.0.0.1,172.18.0.0/16")
    request = SimpleNamespace(
        client=SimpleNamespace(host="203.0.113.5"),
        headers={"x-forwarded-for": "10.0.0.1"},
    )
    assert client_ip(request) == "203.0.113.5"  # type: ignore[arg-type]
