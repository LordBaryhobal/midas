# type: ignore
# ruff: disable[F821, F401]

###> Imports
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, Optional, TypeVar

from midas.ast.location import Location
from midas.lexer.token import Token

###<


###> Preamble
@dataclass(frozen=True, kw_only=True)
class TypeParam:
    location: Location
    name: Token
    bound: Optional[Type]


###<


###> Stmt | Statements
class TypeStmt:
    name: Token
    params: list[TypeParam]
    type: Type


class PropertyStmt:
    name: Token
    type: Type


class ExtendStmt:
    params: list[TypeParam]
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
    args: list[Type]


class ConstraintType:
    type: Type
    constraint: Expr


class ComplexType:
    properties: list[PropertyStmt]


class FunctionType:
    pos_args: list[Argument]
    kw_args: list[Argument]
    returns: Type

    @dataclass(frozen=True, kw_only=True)
    class Argument:
        location: Optional[Location] = None
        name: Optional[Token]
        type: Type
        required: bool


###<
