from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Message(BaseModel):
    message: str


class Paginated(BaseModel, Generic[T]):
    """Standard paginated list response: page of items + unpaginated total."""

    data: list[T]
    count: int
