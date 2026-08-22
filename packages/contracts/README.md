# Shared Contracts

Versioned schemas shared by the API, worker, and dashboard.

Initial contract families:

- Observation and sensor metadata
- Defect types and lifecycle statuses
- Evidence and score components
- Officer verification decisions
- Repair and post-repair validation
- Audit events and provenance

Keep contracts backward-compatible within a major API version. Generated TypeScript types should come from the API schema rather than being handwritten in the web app.