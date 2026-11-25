"""Offline GPS breadcrumb replay, polygon containment, rate-controller drift, and treated-area proof."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import math
from typing import Iterable


@dataclass(frozen=True)
class FieldBoundary:
    block_id: str
    polygon_lat_lon: tuple[tuple[float, float], ...]
    target_rate_per_ha: float
    rate_tolerance_pct: float = 10.0
    swath_width_m: float = 12.0


@dataclass(frozen=True)
class GpsFix:
    job_id: str
    unit_id: str
    seq: int
    recorded_at: datetime
    lat: float
    lon: float
    speed_mps: float
    working: bool
    actual_rate_per_ha: float


@dataclass(frozen=True)
class PlacementSummary:
    job_id: str
    block_id: str
    ordered_fixes: int
    duplicates_dropped: int
    treated_hectares: float
    out_of_boundary_working_fixes: int
    rate_drift_alerts: int
    alerts: tuple[str, ...] = field(default_factory=tuple)


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def point_in_polygon(lat: float, lon: float, polygon: tuple[tuple[float, float], ...]) -> bool:
    """Ray-casting point-in-polygon check over (lat, lon) perimeter ring."""
    if len(polygon) < 3:
        return False
    inside = False
    j = len(polygon) - 1
    for i, (yi, xi) in enumerate(polygon):
        yj, xj = polygon[j]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def replay_offline_breadcrumbs(fixes: Iterable[GpsFix]) -> tuple[list[GpsFix], int]:
    """Order out-of-order offline GPS packets and drop duplicate (unit_id, seq, recorded_at) replays."""
    ordered = sorted(fixes, key=lambda f: (f.unit_id, f.recorded_at, f.seq))
    seen: set[tuple[str, int, datetime]] = set()
    unique: list[GpsFix] = []
    dups = 0
    for fix in ordered:
        k = (fix.unit_id, fix.seq, fix.recorded_at)
        if k in seen:
            dups += 1
            continue
        seen.add(k)
        unique.append(fix)
    return unique, dups


def evaluate_job_placement(
    job_id: str,
    boundary: FieldBoundary,
    fixes: Iterable[GpsFix],
) -> PlacementSummary:
    """Compute verified treated hectares, boundary violations, and rate-controller drift alerts."""
    ordered, dups = replay_offline_breadcrumbs(fixes)
    treated_m2 = 0.0
    out_of_bound = 0
    drift_alerts = 0
    alerts: list[str] = []
    prev_working: GpsFix | None = None

    max_dev = boundary.target_rate_per_ha * (boundary.rate_tolerance_pct / 100.0)

    for fix in ordered:
        if not fix.working:
            prev_working = None
            continue

        if not point_in_polygon(fix.lat, fix.lon, boundary.polygon_lat_lon):
            out_of_bound += 1
            alerts.append(f"off_target_seq:{fix.seq}")

        if abs(fix.actual_rate_per_ha - boundary.target_rate_per_ha) > max_dev:
            drift_alerts += 1
            alerts.append(f"rate_drift_seq:{fix.seq}:{fix.actual_rate_per_ha:.1f}")

        if prev_working is not None and fix.unit_id == prev_working.unit_id:
            dist = _haversine_m(prev_working.lat, prev_working.lon, fix.lat, fix.lon)
            if dist <= 250.0:  # ignore unrealistic offline teleport jumps
                treated_m2 += dist * boundary.swath_width_m
        prev_working = fix

    return PlacementSummary(
        job_id=job_id,
        block_id=boundary.block_id,
        ordered_fixes=len(ordered),
        duplicates_dropped=dups,
        treated_hectares=round(treated_m2 / 10_000.0, 3),
        out_of_boundary_working_fixes=out_of_bound,
        rate_drift_alerts=drift_alerts,
        alerts=tuple(alerts),
    )
