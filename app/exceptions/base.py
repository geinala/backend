"""Base exception classes for API layer."""

from fastapi import status


class APIException(Exception):
    """Base exception for all API errors."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        detail: dict | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}
        super().__init__(self.message)


class JobException(APIException):
    """Base exception for job-related errors."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        detail: dict | None = None,
    ):
        super().__init__(message, status_code, detail)


class JobNotFoundError(JobException):
    """Raised when job is not found."""

    def __init__(self, job_id: str):
        super().__init__(
            f"Job {job_id} not found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"job_id": job_id},
        )


class JobEnqueueError(JobException):
    """Raised when job enqueueing fails."""

    def __init__(self, message: str, original_error: str | None = None):
        detail = {}
        if original_error:
            detail["original_error"] = original_error
        super().__init__(
            message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
        )


class ValidationError(APIException):
    """Raised when validation fails."""

    def __init__(self, message: str, fields: dict | None = None):
        detail = fields or {}
        super().__init__(
            message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )


class ServiceException(APIException):
    """Base exception for service layer errors."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: dict | None = None,
    ):
        super().__init__(message, status_code, detail)
