# type: ignore
# ruff: disable[F821, F401]

###> Imports
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, Optional, TypeVar

from midas.ast.location import Location
from midas.lexer.token import Token

###<


###> Stmt | Statements
class TypeStmt:
    name: Token
    params: list[Param]
    type: Type

    @dataclass(frozen=True, kw_only=True)
    class Param:
        location: Location
        name: Token
        bound: Optional[Type]


class PropertyStmt:
    name: Token
    type: Type


class ExtendStmt:
    type: Type
    operations: list[OpStmt]


class OpStmt:
    name: Token
    operand: Type
    result: Type


class PredicateStmt:
    name: Token
    subject: Token
    type: Type
    condition: Expr


###<


###> Expr | Expressions


class LogicalExpr:
    left: Expr
    operator: Token
    right: Expr


class BinaryExpr:
    left: Expr
    operator: Token
    right: Expr


class UnaryExpr:
    operator: Token
    right: Expr


class GetExpr:
    expr: Expr
    name: Token


class VariableExpr:
    name: Token


class GroupingExpr:
    expr: Expr


class LiteralExpr:
    value: Any


class WildcardExpr:
    token: Token


###<

###> Type | Types


class NamedType:
    name: Token


class GenericType:
    type: Type
    params: list[Type]


class ConstraintType:
    type: Type
    constraint: Expr


class UnionType:
    types: list[Type]


class ComplexType:
    properties: list[PropertyStmt]


###<
