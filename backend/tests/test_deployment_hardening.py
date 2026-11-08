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
    assert names == {"release-stale-reservations", "recover-orphan-stream-messages"}
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
