"""MyApp core module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar, Optional

T = TypeVar("T")


@dataclass
class Person:
    """Person entity."""

    name: str
    age: int

    def greet(self) -> str:
        return f"Hello, {self.name}"

    @classmethod
    def create(cls, name: str, age: int) -> "Person":
        return cls(name, age)


class Repository(Generic[T]):
    """Generic repository."""

    async def get_by_id(self, id: int) -> Optional[T]:
        ...

    async def save(self, entity: T) -> None:
        ...


class Status:
    ACTIVE = 1
    INACTIVE = 2
    PENDING = 3


async def process_data(id: int, data: str) -> dict:
    """Process data asynchronously."""
    return {"id": id, "data": data}
