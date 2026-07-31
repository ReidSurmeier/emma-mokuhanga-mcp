# ADR 0001: Keep Emma as a separate comparative experiment

Status: accepted

## Context

Emma Mokuhanga and the Chuck/woodblock MCP explore related print-planning
questions with different grammars and implementation histories. Treating one
as the other's implementation base would erase the comparison and make
results difficult to attribute.

## Decision

Emma remains an independent repository, domain model, runtime home, and MCP
server. Shared reference cases may be evaluated through an explicit
comparison protocol, but code or findings move between projects only through
reviewed changes that record provenance.

## Consequences

- Neither repository is described as the other's successor.
- A future comparison must define shared inputs, metrics, human evaluation,
  and artifact provenance.
- Consolidation requires a superseding ADR with comparative evidence.
