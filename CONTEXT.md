# Emma Mokuhanga context

## Domain

Emma Mokuhanga is an experimental planning system for interpreting a
reference image as a sequence of mokuhanga impressions. It produces
diagnostic artifacts for human review; it does not authorize machining or
printing.

## Core language

**Reference Image**
: An operator-supplied image copied into a local planning session with
  dimensions, profile metadata, and a content hash.

**Reference Analysis**
: Deterministic palette, edge-density, entropy, complexity, and suggested-grid
  measurements derived from a Reference Image.

**Pigment Profile**
: An uncalibrated planning assumption about a named pigment's color, opacity,
  tint strength, and default load.

**Mask**
: A normalized region assigned a role such as base wash, support, visible
  color, accent, key, or correction. Heuristic planning masks are priors;
  reconstruction masks are image-derived color-cluster regions.

**Color Zone**
: A Mask paired with a pigment recipe and application note for one
  Impression.

**Impression**
: One ordered application of color from one Block. The current plan contract
  requires one Block per Impression, while a Block may contain multiple Color
  Zones.

**Print Plan**
: An ordered set of Masks, Impressions, Blocks, scores, and warnings. It is an
  experimental hypothesis, not a fabrication specification.

**T0 Render**
: A layout preview used to inspect mask coverage and ordering.

**T1 Render**
: An uncalibrated optical-density preview used to inspect plausible
  transparent overprint behavior.

**Reconstruction Workflow**
: A separate image-derived baseline that quantizes the reference into
  disjoint color-cluster plates and exports diagnostic PNG, SVG, cumulative,
  and metric artifacts.

**Geometry Validation**
: Basic detection of path hazards before later export work. Passing it does
  not make a path machinable.

**Review Surface**
: The optional static report and unauthenticated upload server used for local
  or deliberately tailnet-bound review.

## Invariants

- Emma and Chuck are separate comparative experiments.
- A generated Print Plan always carries warnings while its recipes, geometry,
  and physical process remain uncalibrated.
- Every Impression maps to exactly one Block and both identifiers are unique.
- Corpus originals are external inputs; generated files live in ignored
  runtime or report directories.
- Remote review is opt-in and binds to a specific private address. The
  application never assumes that `0.0.0.0` is tailnet-only.

## Current flow

```text
Reference Image
  -> Reference Analysis
  -> heuristic Print Plan
  -> T0/T1 diagnostic renders
  -> human review

Reference Image
  -> image-derived Reconstruction Workflow
  -> diagnostic masks/SVGs/metrics
  -> human review
```

These are parallel experimental paths. Neither currently ends in a CNC-ready
toolpath or a physically validated print recipe.
