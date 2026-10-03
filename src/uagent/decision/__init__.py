"""Opt-in provider-neutral decision layer."""

from .base import DecisionProvider
from .goal_completion import (
    GoalCompletionAttempt,
    GoalCompletionError,
    GoalCompletionEvaluation,
    GoalCompletionFailure,
    build_goal_completion_request,
    evaluate_goal_completion,
    provider_supports_goal_completion,
    provider_uses_atomic_goal_completion,
)
from .models import (
    DecisionAnswer,
    DecisionKind,
    DecisionQuestion,
    DecisionRequest,
    DecisionResult,
)
from .registry import DecisionProviderUnavailableError, create_decision_provider
from .settings import (
    SUPPORTED_DECISION_PROVIDERS,
    DecisionConfigurationError,
    DecisionSettings,
    add_decision_provider_argument,
    configure_decision_settings,
    get_decision_settings,
    normalize_decision_provider,
    resolve_decision_settings,
)

__all__ = [
    "SUPPORTED_DECISION_PROVIDERS",
    "DecisionAnswer",
    "DecisionConfigurationError",
    "DecisionKind",
    "DecisionProvider",
    "DecisionProviderUnavailableError",
    "DecisionQuestion",
    "DecisionRequest",
    "DecisionResult",
    "DecisionSettings",
    "GoalCompletionAttempt",
    "GoalCompletionError",
    "GoalCompletionEvaluation",
    "GoalCompletionFailure",
    "add_decision_provider_argument",
    "configure_decision_settings",
    "create_decision_provider",
    "get_decision_settings",
    "normalize_decision_provider",
    "build_goal_completion_request",
    "evaluate_goal_completion",
    "provider_supports_goal_completion",
    "provider_uses_atomic_goal_completion",
    "resolve_decision_settings",
]
