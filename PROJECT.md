# Project status

## Purpose

Test whether a deterministic, chat-accessible planning pipeline can turn a
reference image into useful experimental guidance for an Emma-style
multi-impression mokuhanga process.

## Current status

Status: active experiment; local, on-demand runtime.

Verified at the documentation baseline:

- the Python behavior suite passes;
- reference analysis, heuristic plan generation, T0/T1 previews, report
  generation, and image-derived reconstruction are implemented;
- GitHub has no Pages site or deployment record for this repository;
- the Droplet Platform inventory has no Emma runtime component; and
- no local Emma process is expected to remain running after verification.

The local review surface is an optional manual process, not a deployed
service. It defaults to loopback and has no authentication.

## Known limitations

- Planning masks are geometric priors rather than image-derived semantic
  regions.
- Plans do not have persistence and load-by-ID tools.
- SVG output is diagnostic raster-run geometry, not final VCarve/CNC output.
- Pigment recipes and optical previews are uncalibrated.
- No physical print series has yet established registration, carving,
  transfer, color, or paper tolerances.
- There is no formal comparison protocol against the separate Chuck MCP.

Track implementation work in GitHub Issues. A change may move one of these
limits only when tests and physical or runtime evidence support it.

## Next work

- Issues #1 and #2 are agent-ready software slices for image-derived masks and
  plan persistence.
- Issue #6 owns review-surface hardening before any supervised runtime.
- Issue #3 needs machine-profile evidence before geometry export work.
- Issues #4 and #5 require human physical-process and comparative-evaluation
  judgment.
