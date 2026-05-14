from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, Optional, TypeVar

from lexer.token import Token

T = TypeVar("T")


# Statements


@dataclass(frozen=True)
class Stmt(ABC):
    @abstractmethod
    def accept(self, visitor: Visitor[T]) -> T: ...

    class Visitor(ABC, Generic[T]):
        @abstractmethod
        def visit_type_stmt(self, stmt: TypeStmt) -> T: ...

        @abstractmethod
        def visit_property_stmt(self, stmt: PropertyStmt) -> T: ...

        @abstractmethod
        def visit_op_stmt(self, stmt: OpStmt) -> T: ...

        @abstractmethod
        def visit_constraint_stmt(self, stmt: ConstraintStmt) -> T: ...


@dataclass(frozen=True)
class TypeStmt(Stmt):
    name: Token
    bases: list[TypeExpr]
    body: Optional[TypeBodyExpr]

    def accept(self, visitor: Stmt.Visitor[T]) -> T:
        return visitor.visit_type_stmt(self)


@dataclass(frozen=True)
class PropertyStmt(Stmt):
    name: Token
    type: TypeExpr

    def accept(self, visitor: Stmt.Visitor[T]) -> T:
        return visitor.visit_property_stmt(self)


@dataclass(frozen=True)
class OpStmt(Stmt):
    left: TypeExpr
    op: Token
    right: TypeExpr
    result: TypeExpr

    def accept(self, visitor: Stmt.Visitor[T]) -> T:
        return visitor.visit_op_stmt(self)


@dataclass(frozen=True)
class ConstraintStmt(Stmt):
    name: Token
    constraint: ConstraintExpr

    def accept(self, visitor: Stmt.Visitor[T]) -> T:
        return visitor.visit_constraint_stmt(self)


# Expressions


@dataclass(frozen=True)
class Expr(ABC):
    @abstractmethod
    def accept(self, visitor: Visitor[T]) -> T: ...

    class Visitor(ABC, Generic[T]):
        @abstractmethod
        def visit_type_expr(self, expr: TypeExpr) -> T: ...

        @abstractmethod
        def visit_constraint_expr(self, expr: ConstraintExpr) -> T: ...

        @abstractmethod
        def visit_type_body_expr(self, expr: TypeBodyExpr) -> T: ...


@dataclass(frozen=True)
class TypeExpr(Expr):
    name: Token
    constraints: list[ConstraintExpr]

    def accept(self, visitor: Expr.Visitor[T]) -> T:
        return visitor.visit_type_expr(self)


@dataclass(frozen=True)
class ConstraintExpr(Expr):
    def accept(self, visitor: Expr.Visitor[T]) -> T:
        return visitor.visit_constraint_expr(self)


@dataclass(frozen=True)
class TypeBodyExpr(Expr):
    properties: list[PropertyStmt]

    def accept(self, visitor: Expr.Visitor[T]) -> T:
        return visitor.visit_type_body_expr(self)
