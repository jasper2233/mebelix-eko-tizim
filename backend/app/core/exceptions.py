from fastapi import HTTPException, status


class NotFoundException(HTTPException):
    def __init__(self, detail: str = "Topilmadi") -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ForbiddenException(HTTPException):
    def __init__(self, detail: str = "Ruxsat berilmagan") -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class UnauthorizedException(HTTPException):
    def __init__(self, detail: str = "Tizimga kirilmagan") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class DuplicateValueException(HTTPException):
    def __init__(self, detail: str = "Takroriy qiymat") -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class RateLimitException(HTTPException):
    def __init__(self, detail: str = "So'rovlar chegarasidan oshib ketdi") -> None:
        super().__init__(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)
