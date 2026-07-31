# ADR 0002: Generated output remains diagnostic

Status: accepted

## Context

The planner produces heuristic masks and uncalibrated pigment assumptions.
The reconstruction path emits SVGs made from raster runs. Neither path models
all constraints required for safe carving, VCarve export, registration, paper,
or physical overprinting.

## Decision

Print Plans, recipes, renders, masks, and SVGs are diagnostic experimental
artifacts. They must carry warnings and must not be represented as CNC-ready,
fabrication-ready, or physically validated.

## Consequences

- Geometry validation detects limited hazards; it does not certify machining.
- Software tests alone cannot close physical-process validation work.
- CNC export requires explicit profiles, tolerance tests, fail-closed
  validation, and a new ADR supported by physical evidence.
