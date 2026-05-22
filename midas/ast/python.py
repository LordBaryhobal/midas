from __future__ import annotations

from abc import ABC, abstractmethod
import ast
from dataclasses import dataclass
from typing import Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class MidasType(ABC):
    @abstractmethod
    def accept(self, visitor: Visitor[T]) -> T: ...

    class Visitor(ABC, Generic[T]):
        @abstractmethod
        def visit_base_type(self, node: BaseType) -> T: ...

        @abstractmethod
        def visit_frame_column(self, node: FrameColumn) -> T: ...

        @abstractmethod
        def visit_frame_type(self, node: FrameType) -> T: ...


@dataclass(frozen=True)
class BaseType(MidasType):
    base: str
    param: Optional[MidasType]
    constraint: Optional[ast.expr] = None

    def accept(self, visitor: MidasType.Visitor[T]) -> T:
        return visitor.visit_base_type(self)


@dataclass(frozen=True)
class FrameColumn(MidasType):
    name: Optional[str]
    type: Optional[MidasType]

    def accept(self, visitor: MidasType.Visitor[T]) -> T:
        return visitor.visit_frame_column(self)


@dataclass(frozen=True)
class FrameType(MidasType):
    columns: list[FrameColumn]

    def accept(self, visitor: MidasType.Visitor[T]) -> T:
        return visitor.visit_frame_type(self)
