# ADR 0003: Keep the review surface local and opt-in

Status: accepted

## Context

The report/upload server has no authentication. Binding it to every network
interface and calling that “over Tailscale” does not ensure tailnet-only
reachability.

## Decision

The server defaults to `127.0.0.1`, limits request bodies, and is not
supervised or deployed. Remote review requires the operator to bind to a
specific Tailscale address and retain host-firewall and tailnet-policy
restrictions.

## Consequences

- `0.0.0.0` is not a documented remote-review mode.
- Public-internet exposure is unsupported.
- Authentication, rate limits, content validation, and service supervision
  remain prerequisites for any future deployment.
