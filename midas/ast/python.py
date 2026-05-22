from __future__ import annotations

from abc import ABC, abstractmethod
import ast
from dataclasses import dataclass
from typing import Generic, Optional, Protocol, TypeVar

T = TypeVar("T")


class HasLocation(Protocol):
    lineno: int
    col_offset: int
    end_lineno: Optional[int]
    end_col_offset: Optional[int]


@dataclass(frozen=True, kw_only=True)
class Location:
    lineno: int
    col_offset: int
    end_lineno: Optional[int]
    end_col_offset: Optional[int]

    @staticmethod
    def from_ast(obj: HasLocation) -> Location:
        return Location(
            lineno=obj.lineno,
            col_offset=obj.col_offset,
            end_lineno=obj.end_lineno,
            end_col_offset=obj.end_col_offset,
        )


@dataclass(frozen=True, kw_only=True)
class Expr(ABC):
    location: Optional[Location] = None

    @abstractmethod
    def accept(self, visitor: Visitor[T]) -> T: ...

    class Visitor(ABC, Generic[T]):
        @abstractmethod
        def visit_base_type(self, node: BaseType) -> T: ...

        @abstractmethod
        def visit_constraint_type(self, node: ConstraintType) -> T: ...

        @abstractmethod
        def visit_frame_column(self, node: FrameColumn) -> T: ...

        @abstractmethod
        def visit_frame_type(self, node: FrameType) -> T: ...

        @abstractmethod
        def visit_function(self, node: Function) -> T: ...

        @abstractmethod
        def visit_function_argument(self, node: FunctionArgument) -> T: ...


@dataclass(frozen=True)
class MidasType(Expr):
    pass


@dataclass(frozen=True)
class BaseType(MidasType):
    base: str
    param: Optional[MidasType]

    def accept(self, visitor: Expr.Visitor[T]) -> T:
        return visitor.visit_base_type(self)


@dataclass(frozen=True)
class ConstraintType(MidasType):
    type: MidasType
    constraint: ast.expr

    def accept(self, visitor: Expr.Visitor[T]) -> T:
        return visitor.visit_constraint_type(self)


@dataclass(frozen=True)
class FrameColumn(MidasType):
    name: Optional[str]
    type: Optional[MidasType]

    def accept(self, visitor: Expr.Visitor[T]) -> T:
        return visitor.visit_frame_column(self)


@dataclass(frozen=True)
class FrameType(MidasType):
    columns: list[FrameColumn]

    def accept(self, visitor: Expr.Visitor[T]) -> T:
        return visitor.visit_frame_type(self)


@dataclass(frozen=True)
class Function(Expr):
    name: str
    posonlyargs: list[FunctionArgument]
    args: list[FunctionArgument]
    kwonlyargs: list[FunctionArgument]
    returns: Optional[MidasType]

    def accept(self, visitor: Expr.Visitor[T]) -> T:
        return visitor.visit_function(self)


@dataclass(frozen=True)
class FunctionArgument(Expr):
    name: Optional[str]
    type: Optional[MidasType]

    def accept(self, visitor: Expr.Visitor[T]) -> T:
        return visitor.visit_function_argument(self)
