from collections import defaultdict
from typing import Dict, Tuple


# (path, status) -> count
_http_requests_total: Dict[Tuple[str, str], int] = defaultdict(int)

# result -> count (for webhook)
_webhook_requests_total: Dict[str, int] = defaultdict(int)

# simple latency buckets in ms
_latency_buckets = {
    "100": 0,
    "500": 0,
    "+Inf": 0,
}
_latency_count = 0


def inc_http_request(path: str, status: int) -> None:
    key = (path, str(status))
    _http_requests_total[key] += 1


def inc_webhook_result(result: str) -> None:
    _webhook_requests_total[result] += 1


def observe_latency_ms(latency_ms: float) -> None:
    global _latency_count
    _latency_count += 1
    if latency_ms <= 100:
        _latency_buckets["100"] += 1
        _latency_buckets["500"] += 1
        _latency_buckets["+Inf"] += 1
    elif latency_ms <= 500:
        _latency_buckets["500"] += 1
        _latency_buckets["+Inf"] += 1
    else:
        _latency_buckets["+Inf"] += 1


def render_metrics() -> str:
    """Return plain text metrics."""
    lines: list[str] = []

    # http_requests_total
    for (path, status), value in _http_requests_total.items():
        lines.append(
            f'http_requests_total{{path="{path}",status="{status}"}} {value}'
        )

    # webhook_requests_total
    for result, value in _webhook_requests_total.items():
        lines.append(
            f'webhook_requests_total{{result="{result}"}} {value}'
        )

    # latency buckets
    for le, value in _latency_buckets.items():
        lines.append(
            f'request_latency_ms_bucket{{le="{le}"}} {value}'
        )
    lines.append(f"request_latency_ms_count {_latency_count}")

    return "\n".join(lines) + "\n"
