from __future__ import annotations

PHASE1_NODE_ORDER = (
    "normalize_input",
    "outline_planner",
    "writer",
    "formatter",
    "schema_validate",
    "save",
)

DIRECT_WRITE_NODE_ORDER = (
    "normalize_input",
    "direct_writer",
    "formatter",
    "schema_validate",
    "save",
)

PIPELINE_VERSIONS = {"outline_then_write": "1", "direct_write": "1"}
