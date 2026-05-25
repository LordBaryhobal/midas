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
class SimpleTypeStmt:
    name: Token
    template: Optional[TemplateExpr]
    base: TypeExpr
    constraint: Optional[Expr]


class ComplexTypeStmt:
    name: Token
    template: Optional[TemplateExpr]
    properties: list[PropertyStmt]


class PropertyStmt:
    name: Token
    type: TypeExpr
    constraint: Optional[Expr]


class ExtendStmt:
    type: TypeExpr
    operations: list[OpStmt]


class OpStmt:
    name: Token
    operand: TypeExpr
    result: TypeExpr


class PredicateStmt:
    name: Token
    subject: Token
    type: TypeExpr
    condition: Expr


###<


###> Expr | Expressions
class SimpleTypeExpr:
    name: Token
    optional: bool


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


class TemplateExpr:
    type: TypeExpr


class TypeExpr:
    name: Token
    template: Optional[TemplateExpr]
    optional: bool


###<
