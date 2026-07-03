from dataclasses import dataclass
from typing import Any, Callable, Optional

import midas.ast.midas as m
from midas.checker.preamble import Preamble
from midas.checker.registry import TypesRegistry
from midas.checker.reporter import FileReporter
from midas.checker.types import Function, Predicate
from midas.lexer.token import TokenType


@dataclass(frozen=True, kw_only=True)
class PartialPredicate(Predicate):
    scope: dict[str, Any]


class Evaluator(m.Expr.Visitor[Any]):
    def __init__(self, types: TypesRegistry, reporter: Optional[FileReporter] = None):
        self.types: TypesRegistry = types
        self.reporter: Optional[FileReporter] = reporter
        self.preamble: Preamble = Preamble(self.types)
        self.scopes: list[dict[str, Any]] = [{}]

    def evaluate(self, expr: m.Expr) -> Any:
        value: Any = expr.accept(self)
        if self.reporter is not None:
            self.reporter.debug(expr.location, f"Value: {value}")
        return value

    def get_value(self, name: str) -> Any:
        scope: dict[str, Any] = self.scopes[-1]
        return scope[name]

    def set_value(self, name: str, value: Any, force_declare: bool = False):
        if not force_declare:
            for scope in reversed(self.scopes):
                if name in scope:
                    scope[name] = value
                    return
        self.scopes[-1][name] = value

    def visit_logical_expr(self, expr: m.LogicalExpr) -> Any:
        def left():
            return self.evaluate(expr.left)

        def right():
            return self.evaluate(expr.right)

        match expr.operator.type:
            case TokenType.AND:
                return left() and right()
            case _:
                raise NotImplementedError

    def visit_binary_expr(self, expr: m.BinaryExpr) -> Any:
        left: Any = self.evaluate(expr.left)
        right: Any = self.evaluate(expr.right)
        match expr.operator.type:
            case TokenType.MINUS:
                return left - right
            case TokenType.STAR:
                return left * right
            case TokenType.SLASH:
                return left / right
            case TokenType.GREATER:
                return left > right
            case TokenType.GREATER_EQUAL:
                return left >= right
            case TokenType.LESS:
                return left < right
            case TokenType.LESS_EQUAL:
                return left <= right
            case TokenType.EQUAL_EQUAL:
                return left == right
            case TokenType.BANG_EQUAL:
                return left != right
            case _:
                raise NotImplementedError

    def visit_unary_expr(self, expr: m.UnaryExpr) -> Any:
        right: Any = self.evaluate(expr.right)
        match expr.operator.type:
            case TokenType.MINUS:
                return -right
            case _:
                raise NotImplementedError

    def visit_call_expr(self, expr: m.CallExpr) -> Any:
        callee: Any = self.evaluate(expr.callee)
        args: list[Any] = [self.evaluate(arg) for arg in expr.arguments]
        kwargs: dict[str, Any] = {
            name: self.evaluate(arg) for name, arg in expr.keywords.items()
        }

        match callee:
            case Predicate():
                return self._evaluate_predicate(callee, args, kwargs)
            case _ if callable(callee):
                return callee(*args, **kwargs)
            case _:
                return NotImplementedError

    def visit_get_expr(self, expr: m.GetExpr) -> Any:
        obj: Any = self.evaluate(expr.expr)
        return getattr(obj, expr.name.lexeme)

    def visit_variable_expr(self, expr: m.VariableExpr) -> Any:
        name: str = expr.name.lexeme
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]

        predicate: Optional[Predicate] = self.types.lookup_predicate(name)
        if predicate is not None:
            if predicate.alias:
                return self.evaluate(predicate.body)
            return predicate

        glob: Optional[Callable] = self.preamble.get_py_func(name)
        if glob is not None:
            return glob
        raise NameError(f"Unknown variable '{name}'")

    def visit_grouping_expr(self, expr: m.GroupingExpr) -> Any:
        return self.evaluate(expr.expr)

    def visit_literal_expr(self, expr: m.LiteralExpr) -> Any:
        return expr.value

    def visit_wildcard_expr(self, expr: m.WildcardExpr) -> Any:
        return self.get_value("_")

    def _evaluate_predicate(
        self, predicate: Predicate, args: list[Any], kwargs: dict[str, Any]
    ) -> Any:
        res: Any = None
        if isinstance(predicate, PartialPredicate):
            self.scopes.append(predicate.scope)
        else:
            self.scopes.append({})
        match predicate.type:
            case Function(returns=Function() as inner):
                self._map_args(predicate.type, args, kwargs)
                res = PartialPredicate(
                    type=inner,
                    body=predicate.body,
                    alias=False,
                    scope=self.scopes[-1],
                )

            case Function():
                self._map_args(predicate.type, args, kwargs)
                res = self.evaluate(predicate.body)

            case _:
                raise NotImplementedError
        self.scopes.pop()
        return res

    def _map_args(self, function: Function, args: list[Any], kwargs: dict[str, Any]):
        positional: list[Function.Parameter] = (
            function.params.pos + function.params.mixed
        )
        keywords: dict[str, Function.Parameter] = {
            param.name: param for param in function.params.mixed + function.params.kw
        }

        for i, arg in enumerate(args):
            param: Function.Parameter = positional[i]
            self.set_value(param.name, arg)

        for name, arg in kwargs.items():
            param: Function.Parameter = keywords[name]
            self.set_value(param.name, arg)
