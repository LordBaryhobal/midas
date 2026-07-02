import ast
from dataclasses import dataclass
from typing import Callable

import midas.ast.python as p

AssertionBuilder = Callable[..., ast.expr]


@dataclass
class Assertion:
    bound_expr: p.Expr
    inputs: list[p.Expr]
    builder: AssertionBuilder
    message: str

    def is_bound_to(self, expr: p.Expr) -> bool:
        return expr == self.bound_expr


class AssertionCollector:
    def __init__(self):
        self.assertions: list[Assertion] = []
        self.definitions: dict[str, ast.stmt] = {}

    def add(
        self,
        bound_expr: p.Expr,
        inputs: list[p.Expr],
        builder: AssertionBuilder,
        message: str,
    ):
        self.assertions.append(
            Assertion(
                bound_expr=bound_expr,
                inputs=inputs,
                builder=builder,
                message=message,
            )
        )

    def define(self, name: str, stmt: ast.stmt):
        if name not in self.definitions:
            self.definitions[name] = stmt

    def get_definitions(self) -> list[ast.stmt]:
        return list(self.definitions.values())

    def get_assertions(self) -> list[Assertion]:
        return self.assertions

    def get_assertions_for(self, expr: p.Expr) -> list[Assertion]:
        return list(filter(lambda a: a.is_bound_to(expr), self.assertions))
