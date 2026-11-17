import pytest

from firmable.costing import call_cost, load_pricing, summarize_rows


def usage(ts, **extra):
    return {"model": "deepseek-v4-flash", "ts": ts, "prompt_tokens": 1_000_000,
            "completion_tokens": 1_000_000, **extra}


def test_submission_uses_declared_off_peak_prices_without_discount():
    band, cost = call_cost(usage("2026-11-12T13:00:00Z"), load_pricing())
    assert band == "off_peak"
    assert cost == pytest.approx(.15 + .60)
    assert call_cost(usage("2026-11-12T02:00:00Z"), load_pricing()) == ("off_peak", cost)


@pytest.mark.parametrize("timestamp,band", [
    ("2026-11-12T01:00:00Z", "peak"), ("2026-11-12T04:00:00Z", "off_peak"),
    ("2026-11-12T06:00:00Z", "peak"), ("2026-11-12T10:00:00Z", "off_peak"),
    ("2026-11-14T02:00:00Z", "off_peak"), ("2026-11-12T08:00:00+07:00", "peak")])
def test_peak_boundaries_weekends_and_timezone(timestamp, band):
    actual, cost = call_cost(usage(timestamp), load_pricing() | {"peak_utc_hours": [[1, 4], [6, 10]]})
    assert actual == band
    assert cost == pytest.approx(1.5 if band == "peak" else .75)


def test_holiday_and_explicit_cache_usage():
    pricing = load_pricing() | {"holiday_dates": ["2026-11-12"]}
    band, cost = call_cost(usage("2026-11-12T02:00:00Z", cached_input_tokens=1_000_000), pricing)
    assert band == "off_peak" and cost == pytest.approx(.003 + .60)


def test_failed_calls_and_unknown_models_are_disclosed():
    report = summarize_rows([usage("2026-11-12T13:00:00Z"),
        usage("2026-11-12T13:00:00Z", prompt_tokens=0, completion_tokens=0, error="timeout"),
        usage("2026-11-12T13:00:00Z", model="unknown")], load_pricing())
    assert report["failed_calls_without_usage"] == 1
    assert report["unpriced_models"] == ["unknown"]
    assert report["bands"]["unpriced"]["input_tokens"] == 1_000_000
