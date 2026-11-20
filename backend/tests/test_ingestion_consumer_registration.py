"""Ingestion plumbing is registered only behind explicit runtime flags."""

import pytest
from app.services.worker import WorkerSettings, process_ingestion_event


@pytest.mark.asyncio
async def test_consumer_is_disabled_by_default() -> None:
    assert [function.__name__ for function in WorkerSettings.functions] == ["worker_probe"]
    assert "publish-ingestion-outbox" not in {job.name for job in WorkerSettings.cron_jobs}
    assert await process_ingestion_event({}, "event-1", "00000000-0000-0000-0000-000000000001") == {
        "status": "disabled"
    }


def test_generated_arq_job_id_is_stable_for_dedup_key() -> None:
    from app.services.outbox_publisher import _arq_job_id

    assert _arq_job_id("create:00000000-0000-0000-0000-000000000001") == (
        "ingestion:00000000-0000-0000-0000-000000000001"
    )
