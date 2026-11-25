from datetime import datetime, timedelta, timezone

from field_gps.telemetry import FieldBoundary, GpsFix, evaluate_job_placement, point_in_polygon

UTC = timezone.utc


def _t(sec: int) -> datetime:
    return datetime(2026, 11, 24, 9, 0, 0, tzinfo=UTC) + timedelta(seconds=sec)


def _block() -> FieldBoundary:
    # Rectangular paddock around Mosgiel-latitude test polygon (~500m x ~400m)
    poly = (
        (-45.8750, 170.3400),
        (-45.8750, 170.3460),
        (-45.8710, 170.3460),
        (-45.8710, 170.3400),
    )
    return FieldBoundary("blk-north-4", poly, target_rate_per_ha=100.0, rate_tolerance_pct=10.0, swath_width_m=15.0)


def test_point_in_polygon():
    b = _block()
    assert point_in_polygon(-45.8730, 170.3430, b.polygon_lat_lon) is True
    assert point_in_polygon(-45.8790, 170.3430, b.polygon_lat_lon) is False


def test_offline_replay_dedup_and_treated_hectares():
    b = _block()
    fixes = [
        GpsFix("j1", "cab-1", 2, _t(10), -45.8730, 170.3420, 8.0, True, 101.0),
        GpsFix("j1", "cab-1", 1, _t(5), -45.8730, 170.3410, 8.0, True, 99.0),
        GpsFix("j1", "cab-1", 1, _t(5), -45.8730, 170.3410, 8.0, True, 99.0),  # duplicate
        GpsFix("j1", "cab-1", 3, _t(15), -45.8730, 170.3430, 8.0, True, 102.0),
        GpsFix("j1", "cab-1", 4, _t(20), -45.8730, 170.3440, 8.0, False, 0.0),  # headland turn off
    ]
    summary = evaluate_job_placement("j1", b, fixes)
    assert summary.ordered_fixes == 4
    assert summary.duplicates_dropped == 1
    assert summary.out_of_boundary_working_fixes == 0
    assert summary.rate_drift_alerts == 0
    assert summary.treated_hectares > 0.2


def test_off_target_and_rate_drift_alerts():
    b = _block()
    fixes = [
        GpsFix("j2", "cab-2", 1, _t(0), -45.8790, 170.3430, 7.5, True, 100.0),  # outside boundary
        GpsFix("j2", "cab-2", 2, _t(5), -45.8730, 170.3430, 7.5, True, 125.0),  # +25% over target
    ]
    summary = evaluate_job_placement("j2", b, fixes)
    assert summary.out_of_boundary_working_fixes == 1
    assert summary.rate_drift_alerts == 1
    assert "off_target_seq:1" in summary.alerts
    assert "rate_drift_seq:2:125.0" in summary.alerts
