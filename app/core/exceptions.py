"""Custom exceptions for TicketPilot AI."""

from fastapi import HTTPException, status


class TicketPilotException(HTTPException):
    """Base exception for TicketPilot."""



class TicketNotFoundError(TicketPilotException):
    def __init__(self, ticket_id: int):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )


class DuplicateTicketError(TicketPilotException):
    def __init__(self, external_id: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ticket with external_id '{external_id}' already exists",
        )


class InvalidStateTransitionError(TicketPilotException):
    def __init__(self, current_state: str, target_state: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition from {current_state} to {target_state}",
        )


class LLMServiceError(TicketPilotException):
    def __init__(self, detail: str = "LLM service unavailable"):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )


class ReprocessNotAllowedError(TicketPilotException):
    def __init__(self, ticket_id: int):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ticket {ticket_id} has a valid AI classification; reprocess is not allowed",
        )
