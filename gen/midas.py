# type: ignore
# ruff: disable[F821, F401]

###> Imports
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
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


class MemberKind(Enum):
    PROPERTY = auto()
    METHOD = auto()


@dataclass(frozen=True, kw_only=True)
class ParamSpec:
    l_paren: Token
    pos: list[FunctionType.Argument]
    mixed: list[FunctionType.Argument]
    kw: list[FunctionType.Argument]


###<


###> Stmt | Statements
class TypeStmt:
    name: Token
    params: list[TypeParam]
    type: Type


class MemberStmt:
    name: Token
    type: Type
    kind: MemberKind


class ExtendStmt:
    name: Token
    params: list[TypeParam]
    members: list[MemberStmt]


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


class CallExpr:
    callee: Expr
    arguments: list[Expr]
    keywords: dict[str, Expr]


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
    members: list[MemberStmt]


class ExtensionType:
    base: Type
    extension: ComplexType


class FunctionType:
    params: ParamSpec
    returns: Type

    @dataclass(frozen=True, kw_only=True)
    class Argument:
        location: Optional[Location] = None
        name: Optional[Token]
        type: Type
        required: bool


###<
