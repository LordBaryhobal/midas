import ast
from dataclasses import dataclass
from typing import Callable

import midas.ast.python as p

AssertionBuilder = Callable[..., ast.expr]
"""A callback function which builds an assertion test given some input expressions"""


@dataclass
class Assertion:
    """Runtime assertion to generate, bound to an expression"""

    bound_expr: p.Expr
    """The expression the assertion is bound to"""

    inputs: list[p.Expr]
    """
    Expressions needed for the assertion
    
    Each expression will be converted by the generator and passed as individual
    arguments to `builder`
    """

    builder: AssertionBuilder
    """The callback to build the assertion test given converted expression from `inputs`"""

    message: str
    """The assertion message"""

    def is_bound_to(self, expr: p.Expr) -> bool:
        """Check whether this assertion is bound to the given expression

        Args:
            expr (p.Expr): the expression

        Returns:
            bool: whether this assertion is bound to `expr`
        """
        return expr == self.bound_expr


class AssertionCollector:
    """Helper class to collect assertions from outside the generator"""

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
        """Add an assertion bound to the given expression

        Args:
            bound_expr (p.Expr): the expression before which the assertion
                must be generated
            inputs (list[p.Expr]): the list of input expressions (see :class:`Assertion`)
            builder (AssertionBuilder): the builder callback (see :class:`Assertion`)
            message (str): the assertion message
        """
        self.assertions.append(
            Assertion(
                bound_expr=bound_expr,
                inputs=inputs,
                builder=builder,
                message=message,
            )
        )

    def remove(self, assertion: Assertion):
        """Remove the given assertion from the collection

        Args:
            assertion (Assertion): the assertion to remove
        """
        try:
            self.assertions.remove(assertion)
        except ValueError:
            pass

    def define(self, name: str, stmt: ast.stmt):
        """Register a statement definition

        This method will only register the first definition of any given name

        Args:
            name (str): the name of the definition
            stmt (ast.stmt): the definition statement, like a function def
        """
        if name not in self.definitions:
            self.definitions[name] = stmt

    def get_definitions(self) -> list[ast.stmt]:
        """Get the list of definitions

        Returns:
            list[ast.stmt]: the list of definitions
        """
        return list(self.definitions.values())

    def get_assertions(self) -> list[Assertion]:
        """Get the list of assertions

        Returns:
            list[Assertion]: the list of assertions
        """
        return self.assertions

    def get_assertions_for(self, expr: p.Expr) -> list[Assertion]:
        """Get the list of assertions bound to a given expression

        Args:
            expr (p.Expr): the expression

        Returns:
            list[Assertion]: the list of assertions bound to `expr`
        """
        return list(filter(lambda a: a.is_bound_to(expr), self.assertions))
