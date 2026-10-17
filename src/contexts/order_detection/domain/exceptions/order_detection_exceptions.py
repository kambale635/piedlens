from shared_kernel.domain_exceptions import DomainException


class InvalidOrderTransitionException(DomainException):
    """Rejects Order status changes outside the graph defined by INV-OD-01.

    See docs/16-business-invariants-and-rules.md and docs/22-error-handling-and-exceptions.md.
    """

    def __init__(self, current_status: str, requested_status: str) -> None:
        """Capture the rejected transition for application-level error mapping."""
        super().__init__(f"Invalid Order transition: {current_status} -> {requested_status}.")
        self.current_status = current_status
        self.requested_status = requested_status


class DetectionCandidateAlreadyReviewedException(DomainException):
    """Rejects a second decision on a candidate, protecting INV-OD-07."""