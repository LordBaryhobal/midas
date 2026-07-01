import ast

import midas.ast.python as p


class AssertionCollector:
    def __init__(self):
        self.assertions: list[tuple[p.Expr, list[ast.expr]]] = []
        self.definitions: dict[str, ast.stmt] = {}

    def add(self, assertion):
        self.assertions.append(assertion)

    def define(self, name: str, stmt: ast.stmt):
        if name not in self.definitions:
            self.definitions[name] = stmt

    def get_definitions(self) -> list[ast.stmt]:
        return list(self.definitions.values())

    def get_assertions(self) -> list[tuple[p.Expr, list[ast.expr]]]:
        return self.assertions
