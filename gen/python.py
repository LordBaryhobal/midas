# type: ignore
# ruff: disable[F821, F401]

###> Imports
import ast
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, Optional, TypeVar

from midas.ast.location import Location

###<


###> Preamble
@dataclass(frozen=True, kw_only=True)
class ParamSpec:
    pos: list[Function.Parameter]
    mixed: list[Function.Parameter]
    kw: list[Function.Parameter]

    @property
    def all(self) -> list[Function.Parameter]:
        return self.pos + self.mixed + self.kw


@dataclass(frozen=True, kw_only=True)
class ImportAlias:
    location: Location
    name: str
    alias: Optional[str] = None

    @property
    def imported_name(self) -> str:
        return self.alias if self.alias is not None else self.name


###<


###> MidasType | Type annotations | node
class BaseType:
    base: str
    args: tuple[MidasType, ...]


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
    params: ParamSpec
    returns: Optional[MidasType]
    body: list[Stmt]

    @dataclass(frozen=True, kw_only=True)
    class Parameter:
        location: Optional[Location] = None
        name: str
        type: Optional[MidasType]
        default: Optional[Expr]


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


class ImportStmt:
    imports: list[ImportAlias]


class FromImportStmt:
    module: Optional[str]
    imports: list[ImportAlias]
    level: int


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
    unsafe: bool


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


class TupleExpr:
    items: tuple[Expr, ...]


class RawExpr:
    expr: ast.expr


###<
