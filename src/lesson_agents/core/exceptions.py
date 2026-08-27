class LessonPlannerError(Exception):
    """Base error for the lesson planner."""


class ModelProviderError(LessonPlannerError):
    """Raised when a model provider cannot return the requested response."""


class PipelineRunError(LessonPlannerError):
    """Raised after a failed run has been persisted."""


class ToolExecutionError(LessonPlannerError):
    """Raised when a requested tool call is invalid or unsafe."""

