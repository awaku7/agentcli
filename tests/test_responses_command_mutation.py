from __future__ import annotations

from uagent.runtime.responses_command_mutation import ResponsesCommandMutationService
from uagent.runtime.responses_command_state import ResponsesCommandState


def test_explicit_cancel_clears_continuation_after_success() -> None:
    service = ResponsesCommandMutationService(
        ResponsesCommandState(active_response_id="active-1")
    )

    plan = service.after_cancel("other-1", explicit_id=True)

    assert plan.operation == "cancel"
    assert plan.clear_continuation is True


def test_implicit_cancel_only_clears_current_response() -> None:
    service = ResponsesCommandMutationService(
        ResponsesCommandState(active_response_id="active-1")
    )

    assert service.after_cancel("active-1", explicit_id=False).clear_continuation is True
    assert service.after_cancel("other-1", explicit_id=False).clear_continuation is False


def test_delete_clears_only_current_continuation() -> None:
    service = ResponsesCommandMutationService(
        ResponsesCommandState(previous_response_id="previous-1")
    )

    assert service.after_delete("previous-1").clear_continuation is True
    assert service.after_delete("other-1").clear_continuation is False
