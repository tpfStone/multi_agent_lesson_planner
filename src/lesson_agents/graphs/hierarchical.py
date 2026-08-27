"""Hierarchical Phase 2 contract placeholder; no scheduling is implemented."""

HIERARCHICAL_RESERVED_DEPENDENCIES = {
    "supervisor": (),
    "objectives_worker": ("supervisor",),
    "activities_worker": ("objectives_worker",),
    "assessment_worker": ("objectives_worker",),
    "synthesizer": ("activities_worker", "assessment_worker"),
    "reviewer": ("synthesizer",),
    "formatter": ("reviewer",),
}


def build_hierarchical_graph():
    raise NotImplementedError("Hierarchical orchestration is reserved for Phase 2")

