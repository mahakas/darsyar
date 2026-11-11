"""متریک‌های سبک و درون‌فرایندی (Slice F).

پیاده‌سازی مینیمال و Prometheus-compatible بدون وابستگی خارجی. مطالب «low-cardinality»
هستند و هرگز user/conversation/message/reservation id یا text خام را به‌عنوان برچسب
نمی‌گیرند. متریک‌های مالی فقط پس از تأیید نتیجهٔ DB (settle/release) به‌روز می‌شوند.
"""

import threading
from collections import defaultdict
from typing import Any

_LOCK = threading.Lock()
LabelKey = tuple[tuple[str, str], ...]


class Counter:
    def __init__(self, name: str, help_text: str) -> None:
        self.name = name
        self.help = help_text
        self._values: dict[LabelKey, int] = defaultdict(int)

    def inc(self, labels: dict[str, str] | None = None) -> None:
        key = self._key(labels)
        with _LOCK:
            self._values[key] += 1

    def _key(self, labels: dict[str, str] | None) -> LabelKey:
        if not labels:
            return ()
        return tuple(sorted(labels.items()))

    def snapshot(self) -> dict[LabelKey, int]:
        with _LOCK:
            return dict(self._values)


class Gauge:
    def __init__(self, name: str, help_text: str) -> None:
        self.name = name
        self.help = help_text
        self._values: dict[LabelKey, float] = defaultdict(float)

    def inc(self, labels: dict[str, str] | None = None, amount: float = 1.0) -> None:
        self._apply(labels, amount)

    def dec(self, labels: dict[str, str] | None = None, amount: float = 1.0) -> None:
        self._apply(labels, -amount)

    def set(self, labels: dict[str, str] | None, value: float) -> None:
        key = self._key(labels)
        with _LOCK:
            self._values[key] = value

    def _apply(self, labels: dict[str, str] | None, amount: float) -> None:
        key = self._key(labels)
        with _LOCK:
            self._values[key] += amount

    def _key(self, labels: dict[str, str] | None) -> LabelKey:
        if not labels:
            return ()
        return tuple(sorted(labels.items()))

    def snapshot(self) -> dict[LabelKey, float]:
        with _LOCK:
            return dict(self._values)


class Histogram:
    _BUCKETS = (0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, float("inf"))

    def __init__(self, name: str, help_text: str) -> None:
        self.name = name
        self.help = help_text
        self._counts: dict[LabelKey, list[int]] = defaultdict(lambda: [0] * len(self._BUCKETS))
        self._sums: dict[LabelKey, float] = defaultdict(float)
        self._total: dict[LabelKey, int] = defaultdict(int)

    def observe(self, value: float, labels: dict[str, str] | None = None) -> None:
        key = self._key(labels)
        with _LOCK:
            self._sums[key] += value
            self._total[key] += 1
            for i, upper in enumerate(self._BUCKETS):
                if value <= upper:
                    self._counts[key][i] += 1
                    break

    def _key(self, labels: dict[str, str] | None) -> LabelKey:
        if not labels:
            return ()
        return tuple(sorted(labels.items()))

    def snapshot(self) -> dict[str, Any]:
        with _LOCK:
            buckets: dict[LabelKey, list[int]] = {k: list(v) for k, v in self._counts.items()}
            sums: dict[LabelKey, float] = dict(self._sums)
            totals: dict[LabelKey, int] = dict(self._total)
            return {"buckets": buckets, "sum": sums, "count": totals}


class MetricsRegistry:
    def __init__(self) -> None:
        self.outbox_publisher_invocations = Counter("outbox_publisher_invocations", "Outbox publisher run counts by source")
        self.outbox_reconciliation_attempts = Counter("outbox_reconciliation_attempts", "Outbox reconciliation run counts")
        self.outbox_events_discovered = Counter("outbox_events_discovered", "Eligible outbox events claimed")
        self.outbox_events_published = Counter("outbox_events_published", "Outbox events published to ARQ")
        self.outbox_events_deferred = Counter("outbox_events_deferred", "Outbox events deferred on transient Redis failure")
        self.outbox_events_failed = Counter("outbox_events_failed", "Outbox events failed permanently (contract)")
        self.outbox_duplicate_enqueue = Counter("outbox_duplicate_enqueue", "Duplicate ARQ enqueue tolerated")
        self.outbox_pg_commit_failure_after_enqueue = Counter("outbox_pg_commit_failure_after_enqueue", "Postgres commit failure after enqueue")
        self.chat_active = Gauge("chat_streams_active", "Active streaming chat requests")
        self.chat_started = Counter("chat_streams_started", "Accepted stream requests")
        self.chat_completed = Counter("chat_streams_completed", "Successfully completed streams")
        self.chat_failed = Counter("chat_streams_failed", "Failed streams")
        self.chat_cancelled = Counter("chat_streams_cancelled", "Cancelled streams")
        self.provider_errors = Counter("chat_provider_errors", "Provider failure classes")
        self.replays = Counter("chat_stream_replays", "Replay/reconnect activity")
        self.financial_outcome = Counter("chat_financial_outcome", "Confirmed settle/release outcomes")
        self.shutdown_forced_cancellations = Counter("shutdown_forced_cancellations", "Streams cancelled after grace timeout")
        self.stream_duration = Histogram("chat_stream_duration_seconds", "Total stream duration")
        self.ttfb = Histogram("chat_time_to_first_billable_token_seconds", "Provider first-output latency")
        self.provider_duration = Histogram("chat_provider_duration_seconds", "Provider latency")
        self.shutdown_drain = Histogram("shutdown_drain_duration_seconds", "Shutdown behavior")

    def as_prometheus_text(self) -> str:
        lines = ["# HELP darsyar backend metrics", "# TYPE darsyar_counter counter"]
        counters: list[Counter] = [
            self.outbox_publisher_invocations,
            self.outbox_reconciliation_attempts,
            self.outbox_events_discovered,
            self.outbox_events_published,
            self.outbox_events_deferred,
            self.outbox_events_failed,
            self.outbox_duplicate_enqueue,
            self.outbox_pg_commit_failure_after_enqueue,
            self.chat_started,
            self.chat_completed,
            self.chat_failed,
            self.chat_cancelled,
            self.provider_errors,
            self.replays,
            self.financial_outcome,
            self.shutdown_forced_cancellations,
        ]
        for metric in counters:
            for labels, int_val in metric.snapshot().items():
                lines.append(f"{metric.name}{self._fmt_labels(labels)} {int(int_val)}")
        gauge_metric = self.chat_active
        for labels, float_val in gauge_metric.snapshot().items():
            lines.append(f"{gauge_metric.name}{self._fmt_labels(labels)} {float_val}")
        for hist in (self.stream_duration, self.ttfb, self.provider_duration, self.shutdown_drain):
            snap = hist.snapshot()
            for labels, counts in snap["buckets"].items():
                for _i, (upper, c) in enumerate(zip(Histogram._BUCKETS, counts, strict=True)):
                    le = "inf" if upper == float("inf") else f"{upper:g}"
                    lines.append(f"{hist.name}_bucket{self._fmt_labels(labels, extra={'le': le})} {int(c)}")
            for labels, s in snap["sum"].items():
                lines.append(f"{hist.name}_sum{self._fmt_labels(labels)} {s}")
            for labels, c in snap["count"].items():
                lines.append(f"{hist.name}_count{self._fmt_labels(labels)} {int(c)}")
        return "\n".join(lines)

    @staticmethod
    def _fmt_labels(labels: LabelKey, extra: dict[str, str] | None = None) -> str:
        if not labels and not extra:
            return ""
        merged = list(labels)
        if extra:
            merged.extend(sorted(extra.items()))
        return "{" + ",".join(f'{k}="{v}"' for k, v in merged) + "}"


METRICS = MetricsRegistry()
