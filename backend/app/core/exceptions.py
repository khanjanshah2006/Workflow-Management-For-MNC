class AppException(Exception):
    """Base exception for application errors."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class NotFoundError(AppException):
    """Raised when a requested resource is not found."""
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message=message, status_code=404)


class ForbiddenError(AppException):
    """Raised when an authenticated actor is not permitted to perform an action."""
    def __init__(self, message: str = "Access forbidden: insufficient role permissions"):
        super().__init__(message=message, status_code=403)


class ValidationError(AppException):
    """Raised when an input or state transition validation fails."""
    def __init__(self, message: str = "Validation failed"):
        super().__init__(message=message, status_code=422)


class UnauthorizedError(AppException):
    """Raised when authentication credentials are missing or invalid."""
    def __init__(self, message: str = "Authentication credentials required"):
        super().__init__(message=message, status_code=401)

