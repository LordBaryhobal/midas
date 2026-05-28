import logging
from pathlib import Path
from typing import Optional

import midas.ast.midas as m
import midas.ast.python as p
from midas.checker.environment import Environment
from midas.checker.operators import OPERATOR_METHODS
from midas.checker.types import BaseType, Type, UnknownType
from midas.lexer.midas import MidasLexer
from midas.lexer.token import Token
from midas.parser.midas import MidasParser
from midas.resolver.midas import MidasResolver


class Checker(
    p.Stmt.Visitor[None],
    p.Expr.Visitor[Type],
    p.MidasType.Visitor[Type],
):
    def __init__(self, locals: dict[p.Expr, int], base_dir: Path):
        self.logger: logging.Logger = logging.getLogger("Checker")
        self.base_dir: Path = base_dir
        self.ctx: MidasResolver = MidasResolver()
        self.global_env: Environment = Environment()
        self.env: Environment = self.global_env
        self.locals: dict[p.Expr, int] = locals

    def evaluate(self, expr: p.Expr) -> Type:
        return expr.accept(self)

    def check(self, statements: list[p.Stmt]) -> None:
        for stmt in statements:
            stmt.accept(self)

        self.logger.debug(f"Final environment: {self.env.flat_dict()}")

    def look_up_variable(self, name: str, expr: p.Expr) -> Optional[Type]:
        distance: Optional[int] = self.locals.get(expr)
        if distance is not None:
            return self.env.get_at(distance, name)
        return self.global_env.get(name)

    def parse_midas_import(self, expr: p.CallExpr) -> Optional[Path]:
        match expr:
            case p.CallExpr(
                callee=p.GetExpr(
                    object=p.VariableExpr(name="midas"),
                    name="using",
                ),
                arguments=[
                    p.LiteralExpr(value=path),
                ],
            ):
                return Path(path)
        return None

    def import_midas(self, path: Path) -> None:
        self.logger.debug(f"Importing type definitions from {path}")
        path = (self.base_dir / path).resolve()
        lexer: MidasLexer = MidasLexer(path.read_text())
        tokens: list[Token] = lexer.process()
        parser: MidasParser = MidasParser(tokens)
        stmts: list[m.Stmt] = parser.parse()
        self.ctx.resolve(stmts)
        self.logger.debug(f"Midas types: {self.ctx._types}")
        self.logger.debug(f"Midas operations: {self.ctx._operations}")

    def visit_expression_stmt(self, stmt: p.ExpressionStmt) -> None:
        self.evaluate(stmt.expr)

    def visit_function(self, stmt: p.Function) -> None: ...

    def visit_type_assign(self, stmt: p.TypeAssign) -> None:
        # TODO check not yet defined locally
        type: Type = stmt.type.accept(self)
        self.env.define(stmt.name, type)

    def visit_assign_stmt(self, stmt: p.AssignStmt) -> None:
        value: Type = self.evaluate(stmt.value)
        for target in stmt.targets:
            if not isinstance(target, p.VariableExpr):
                self.logger.warning(f"Unsupported assignment to {target}")
                continue
            name: str = target.name
            var_type: Optional[Type] = self.look_up_variable(name, target)

            if var_type is None:
                self.env.define(name, value)
            else:
                # TODO: implement real comparison method
                if var_type != value:
                    raise ValueError(
                        f"Cannot assign {value} to {name} of type {var_type}"
                    )

    def visit_binary_expr(self, expr: p.BinaryExpr) -> Type:
        method: Optional[str] = OPERATOR_METHODS.get(expr.operator.__class__)
        if method is None:
            self.logger.warning(f"Unsupported operator {expr.operator}")
            return UnknownType()
        left: Type = self.evaluate(expr.left)
        right: Type = self.evaluate(expr.right)

        result: Type = self.ctx.get_operation_result(left, method, right)
        return result

    def visit_compare_expr(self, expr: p.CompareExpr) -> Type: ...

    def visit_unary_expr(self, expr: p.UnaryExpr) -> Type: ...

    def visit_call_expr(self, expr: p.CallExpr) -> Type:
        if path := self.parse_midas_import(expr):
            self.import_midas(path)
            return UnknownType()
        callee: Type = self.evaluate(expr.callee)
        arguments: list[Type] = [self.evaluate(arg) for arg in expr.arguments]
        keywords: dict[str, Type] = {
            name: self.evaluate(arg) for name, arg in expr.keywords.items()
        }
        return UnknownType()

    def visit_get_expr(self, expr: p.GetExpr) -> Type: ...

    def visit_literal_expr(self, expr: p.LiteralExpr) -> Type:
        match expr.value:
            case bool():  # Must be before int
                return self.ctx.get_type("bool")
            case int():
                return self.ctx.get_type("int")
            case float():
                return self.ctx.get_type("float")
            case str():
                return self.ctx.get_type("str")
            case _:
                return UnknownType()

    def visit_variable_expr(self, expr: p.VariableExpr) -> Type:
        return self.look_up_variable(expr.name, expr) or UnknownType()

    def visit_logical_expr(self, expr: p.LogicalExpr) -> Type: ...

    def visit_set_expr(self, expr: p.SetExpr) -> Type: ...

    def visit_base_type(self, node: p.BaseType) -> Type:
        return self.ctx.get_type(node.base)

    def visit_constraint_type(self, node: p.ConstraintType) -> Type: ...

    def visit_frame_column(self, node: p.FrameColumn) -> Type: ...

    def visit_frame_type(self, node: p.FrameType) -> Type: ...
