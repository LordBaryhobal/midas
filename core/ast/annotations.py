from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, Optional, TypeVar

from lexer.token import Token

T = TypeVar("T")


@dataclass(frozen=True)
class Stmt(ABC):
    @abstractmethod
    def accept(self, visitor: Visitor[T]) -> T: ...

    class Visitor(ABC, Generic[T]):
        @abstractmethod
        def visit_annotation_stmt(self, stmt: AnnotationStmt) -> T: ...


@dataclass(frozen=True)
class AnnotationStmt(Stmt):
    name: Token
    schema: Optional[SchemaExpr]

    def accept(self, visitor: Stmt.Visitor[T]) -> T:
        return visitor.visit_annotation_stmt(self)


@dataclass(frozen=True)
class Expr(ABC):
    @abstractmethod
    def accept(self, visitor: Visitor[T]) -> T: ...

    class Visitor(ABC, Generic[T]):
        @abstractmethod
        def visit_wildcard_expr(self, expr: WildcardExpr) -> T: ...

        @abstractmethod
        def visit_literal_expr(self, expr: LiteralExpr) -> T: ...

        @abstractmethod
        def visit_type_expr(self, expr: TypeExpr) -> T: ...

        @abstractmethod
        def visit_constraint_expr(self, expr: ConstraintExpr) -> T: ...

        @abstractmethod
        def visit_schema_expr(self, expr: SchemaExpr) -> T: ...

        @abstractmethod
        def visit_schema_element_expr(self, expr: SchemaElementExpr) -> T: ...


@dataclass(frozen=True)
class WildcardExpr(Expr):
    token: Token

    def accept(self, visitor: Expr.Visitor[T]) -> T:
        return visitor.visit_wildcard_expr(self)


@dataclass(frozen=True)
class LiteralExpr(Expr):
    value: Any

    def accept(self, visitor: Expr.Visitor[T]) -> T:
        return visitor.visit_literal_expr(self)


@dataclass(frozen=True)
class TypeExpr(Expr):
    name: Token
    constraints: list[ConstraintExpr]

    def accept(self, visitor: Expr.Visitor[T]) -> T:
        return visitor.visit_type_expr(self)


@dataclass(frozen=True)
class ConstraintExpr(Expr):
    left: Expr
    op: Token
    right: Expr

    def accept(self, visitor: Expr.Visitor[T]) -> T:
        return visitor.visit_constraint_expr(self)


@dataclass(frozen=True)
class SchemaExpr(Expr):
    left: Token
    elements: list[Expr]
    right: Token

    def accept(self, visitor: Expr.Visitor[T]) -> T:
        return visitor.visit_schema_expr(self)


@dataclass(frozen=True)
class SchemaElementExpr(Expr):
    name: Optional[Token]
    type: Optional[Expr]

    def accept(self, visitor: Expr.Visitor[T]) -> T:
        return visitor.visit_schema_element_expr(self)
