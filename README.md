# Offline Field GPS Telemetry & Proof-of-Placement Engine

Offline-resilient vehicle/aircraft GPS breadcrumb replay, polygon boundary containment, and rate-controller drift verification for precision field operations.

## Problem

Field contracting, agriculture, horticulture, and aerial operations rely on cab terminals and mobile apps operating across dead-zone coverage. When units reconnect and flush buffered 5-second telemetry logs, cloud backends must handle:

1. **Out-of-order & duplicate GPS breadcrumbs** replayed from intermittent cellular uploads.
2. **Boundary proof-of-placement** checking active spray/spread track points against assigned paddock/block polygons to flag off-target drift.
3. **Rate-controller drift & speed anomalies** detecting under/over-application against job target rates and calculating verified treated area.

## Running Tests

```bash
PYTHONPATH=src python3 -m pytest -v
```
