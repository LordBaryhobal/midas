# type: ignore
# ruff: disable[F821, F401]

###> Imports
import ast
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, Optional, TypeVar

from midas.ast.location import Location

###<


###> MidasType | Type annotations | node
class BaseType:
    base: str
    param: Optional[MidasType]


class ConstraintType:
    type: MidasType
    constraint: ast.expr


class FrameColumn:
    name: Optional[str]
    type: Optional[MidasType]


class FrameType:
    columns: list[FrameColumn]


###<


###> Stmt | Statements
class ExpressionStmt:
    expr: Expr


class Function:
    name: str
    posonlyargs: list[Argument]
    args: list[Argument]
    sink: Optional[Argument]
    kwonlyargs: list[Argument]
    kw_sink: Optional[Argument]
    returns: Optional[MidasType]
    body: list[Stmt]

    @dataclass(frozen=True, kw_only=True)
    class Argument:
        location: Optional[Location] = None
        name: str
        type: Optional[MidasType]
        default: Optional[Expr]

    @property
    def all_args(self) -> list[Argument]:
        return self.posonlyargs + self.args + self.kwonlyargs


class TypeAssign:
    name: str
    type: MidasType


class AssignStmt:
    targets: list[Expr]
    value: Expr


class ReturnStmt:
    value: Optional[Expr]


class IfStmt:
    test: Expr
    body: list[Stmt]
    orelse: list[Stmt]


class Pass:
    pass


class ForStmt:
    target: Expr
    iterator: Expr
    body: list[Stmt]


class RawStmt:
    stmt: ast.stmt


###<


###> Expr | Expressions
class BinaryExpr:
    left: Expr
    operator: ast.operator
    right: Expr


class CompareExpr:
    left: Expr
    operator: ast.cmpop
    right: Expr


class UnaryExpr:
    operator: ast.unaryop
    right: Expr


class CallExpr:
    callee: Expr
    arguments: list[Expr]
    keywords: dict[str, Expr]


class GetExpr:
    object: Expr
    name: str


class LiteralExpr:
    value: Any


class VariableExpr:
    name: str


class LogicalExpr:
    left: Expr
    operator: ast.boolop
    right: Expr


class CastExpr:
    type: MidasType
    expr: Expr


class TernaryExpr:
    test: Expr
    if_true: Expr
    if_false: Expr


class ListExpr:
    items: list[Expr]


class DictExpr:
    keys: list[Optional[Expr]]
    values: list[Expr]


class SubscriptExpr:
    object: Expr
    index: Expr


class SliceExpr:
    lower: Optional[Expr]
    upper: Optional[Expr]
    step: Optional[Expr]


class RawExpr:
    expr: ast.expr


###<
