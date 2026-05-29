import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import midas.ast.midas as m
import midas.ast.python as p
from midas.ast.location import Location
from midas.checker.diagnostic import Diagnostic, DiagnosticType
from midas.checker.environment import Environment
from midas.checker.operators import OPERATOR_METHODS
from midas.checker.types import Function, Type, UnitType, UnknownType
from midas.lexer.midas import MidasLexer
from midas.lexer.token import Token
from midas.parser.midas import MidasParser
from midas.resolver.midas import MidasResolver


class ReturnException(Exception):
    pass


@dataclass(frozen=True, kw_only=True)
class MappedArgument:
    expr: p.Expr
    type: Type
    argument: Function.Argument


class Checker(
    p.Stmt.Visitor[None],
    p.Expr.Visitor[Type],
    p.MidasType.Visitor[Type],
):
    def __init__(self, locals: dict[p.Expr, int], file_path: Path):
        self.logger: logging.Logger = logging.getLogger("Checker")
        self.file_path: Path = file_path
        self.ctx: MidasResolver = MidasResolver()
        self.global_env: Environment = Environment()
        self.env: Environment = self.global_env
        self.locals: dict[p.Expr, int] = locals
        self.diagnostics: list[Diagnostic] = []

    def diagnostic(self, type: DiagnosticType, location: Location, message: str):
        self.diagnostics.append(
            Diagnostic(
                file_path=self.file_path,
                location=location,
                type=type,
                message=message,
            )
        )

    def error(self, location: Location, message: str):
        self.diagnostic(
            type=DiagnosticType.ERROR,
            location=location,
            message=message,
        )

    def warning(self, location: Location, message: str):
        self.diagnostic(
            type=DiagnosticType.WARNING,
            location=location,
            message=message,
        )

    def info(self, location: Location, message: str):
        self.diagnostic(
            type=DiagnosticType.INFO,
            location=location,
            message=message,
        )

    def evaluate(self, expr: p.Expr) -> Type:
        return expr.accept(self)

    def evaluate_block(self, block: list[p.Stmt], env: Environment) -> None:
        previous_env: Environment = self.env
        self.env = env
        for stmt in block:
            try:
                stmt.accept(self)
            except ReturnException:
                break
        self.env = previous_env

    def check(self, statements: list[p.Stmt]) -> list[Diagnostic]:
        self.diagnostics = []
        for stmt in statements:
            stmt.accept(self)

        self.logger.debug(f"Final environment: {self.env.flat_dict()}")
        return self.diagnostics

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
        path = (self.file_path.parent / path).resolve()
        lexer: MidasLexer = MidasLexer(path.read_text())
        tokens: list[Token] = lexer.process()
        parser: MidasParser = MidasParser(tokens)
        stmts: list[m.Stmt] = parser.parse()
        self.ctx.resolve(stmts)
        self.logger.debug(f"Midas types: {self.ctx._types}")
        self.logger.debug(f"Midas operations: {self.ctx._operations}")

    def visit_expression_stmt(self, stmt: p.ExpressionStmt) -> None:
        self.evaluate(stmt.expr)

    def visit_function(self, stmt: p.Function) -> None:
        env: Environment = Environment(self.env)
        pos_args: list[Function.Argument] = []
        args: list[Function.Argument] = []
        kw_args: list[Function.Argument] = []

        def eval_arg_type(arg: p.Function.Argument) -> Type:
            if arg.type is not None:
                return arg.type.accept(self)
            if arg.default is not None:
                return arg.default.accept(self)
            return UnknownType()

        for arg in stmt.posonlyargs:
            pos_args.append(
                Function.Argument(
                    name=arg.name,
                    type=eval_arg_type(arg),
                    required=arg.default is None,
                )
            )
        for arg in stmt.args:
            args.append(
                Function.Argument(
                    name=arg.name,
                    type=eval_arg_type(arg),
                    required=arg.default is None,
                )
            )
        for arg in stmt.kwonlyargs:
            kw_args.append(
                Function.Argument(
                    name=arg.name,
                    type=eval_arg_type(arg),
                    required=arg.default is None,
                )
            )

        for arg in pos_args + args + kw_args:
            env.define(arg.name, arg.type)

        self.evaluate_block(stmt.body, env)
        inferred_return: Type = UnknownType()
        if len(env.return_types) == 1:
            inferred_return = list(env.return_types)[0]
        elif len(env.return_types) > 1:
            self.error(
                stmt.location,
                f"Mixed return types: {env.return_types}",
            )
        returns: Type = UnknownType()
        if stmt.returns is not None:
            returns = stmt.returns.accept(self)
            if returns != inferred_return:
                self.error(
                    stmt.returns.location,
                    f"Return type mismatch, annotated {returns} but returns {inferred_return}",
                )
        else:
            returns = inferred_return

        # TODO: handle *args and **kwargs sinks
        function: Function = Function(
            name=stmt.name,
            pos_args=pos_args,
            args=args,
            kw_args=kw_args,
            returns=returns,
        )
        self.env.define(stmt.name, function)

    def visit_type_assign(self, stmt: p.TypeAssign) -> None:
        # TODO check not yet defined locally
        type: Type = stmt.type.accept(self)
        self.env.define(stmt.name, type)

    def visit_assign_stmt(self, stmt: p.AssignStmt) -> None:
        value: Type = self.evaluate(stmt.value)
        for target in stmt.targets:
            if not isinstance(target, p.VariableExpr):
                self.logger.warning(f"Unsupported assignment to {target}")
                self.warning(target.location, f"Unsupported assignment to {target}")
                continue
            name: str = target.name
            var_type: Optional[Type] = self.look_up_variable(name, target)

            if var_type is None:
                self.env.define(name, value)
            else:
                # TODO: implement real comparison method
                if var_type != value:
                    self.error(
                        stmt.location,
                        f"Cannot assign {value} to {name} of type {var_type}",
                    )

    def visit_return_stmt(self, stmt: p.ReturnStmt) -> None:
        type: Type = stmt.value.accept(self) if stmt.value is not None else UnitType()
        self.env.return_types.add(type)
        raise ReturnException()

    def visit_binary_expr(self, expr: p.BinaryExpr) -> Type:
        method: Optional[str] = OPERATOR_METHODS.get(expr.operator.__class__)
        if method is None:
            self.logger.warning(f"Unsupported operator {expr.operator}")
            self.warning(expr.location, f"Unsupported operator {expr.operator}")
            return UnknownType()
        left: Type = self.evaluate(expr.left)
        right: Type = self.evaluate(expr.right)

        result: Optional[Type] = self.ctx.get_operation_result(left, method, right)
        if result is None:
            self.error(
                expr.location,
                f"Undefined operation {method} between {left} and {right}",
            )
            return UnknownType()
        return result

    def visit_compare_expr(self, expr: p.CompareExpr) -> Type: ...

    def visit_unary_expr(self, expr: p.UnaryExpr) -> Type: ...

    def visit_call_expr(self, expr: p.CallExpr) -> Type:
        if path := self.parse_midas_import(expr):
            self.import_midas(path)
            return UnknownType()
        callee: Type = self.evaluate(expr.callee)
        if not isinstance(callee, Function):
            self.error(expr.callee.location, "Callee is not a function")
            return UnknownType()
        function: Function = callee
        mapped: list[MappedArgument] = self.map_call_arguments(function, expr)
        for arg in mapped:
            if arg.type != arg.argument.type:
                self.error(
                    arg.expr.location,
                    f"Wrong type for argument '{arg.argument.name}', expected {arg.argument.type}, got {arg.type}",
                )
        return function.returns

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
                self.warning(expr.location, f"Unknown literal {expr}")
                return UnknownType()

    def visit_variable_expr(self, expr: p.VariableExpr) -> Type:
        return self.look_up_variable(expr.name, expr) or UnknownType()

    def visit_logical_expr(self, expr: p.LogicalExpr) -> Type: ...

    def visit_set_expr(self, expr: p.SetExpr) -> Type: ...

    def visit_cast_expr(self, expr: p.CastExpr) -> Type:
        return expr.type.accept(self)

    def visit_base_type(self, node: p.BaseType) -> Type:
        return self.ctx.get_type(node.base)

    def visit_constraint_type(self, node: p.ConstraintType) -> Type: ...

    def visit_frame_column(self, node: p.FrameColumn) -> Type: ...

    def visit_frame_type(self, node: p.FrameType) -> Type: ...

    def map_call_arguments(
        self, function: Function, call: p.CallExpr
    ) -> list[MappedArgument]:
        positional: list[tuple[p.Expr, Type]] = [
            (arg, self.evaluate(arg)) for arg in call.arguments
        ]
        keywords: dict[str, tuple[p.Expr, Type]] = {
            name: (arg, self.evaluate(arg)) for name, arg in call.keywords.items()
        }
        set_args: set[str] = set()

        required_positional: list[str] = [
            arg.name for arg in function.pos_args + function.args if arg.required
        ]
        required_keyword: list[str] = [
            arg.name for arg in function.kw_args if arg.required
        ]

        mapped: list[MappedArgument] = []

        pos_params: list[Function.Argument] = list(function.pos_args)
        mixed_params: list[Function.Argument] = list(function.args)
        kw_params: dict[str, Function.Argument] = {
            arg.name: arg for arg in function.kw_args
        }

        # TODO: handle *args and **kwargs sinks
        for arg in positional:
            param: Function.Argument
            if len(pos_params) != 0:
                param = pos_params.pop(0)
            elif len(mixed_params) != 0:
                param = mixed_params.pop(0)
            else:
                self.error(arg[0].location, "Too many positional arguments")
                break
            name: str = param.name
            if name in required_positional:
                required_positional.remove(name)
            if name in required_keyword:
                required_keyword.remove(name)
            set_args.add(name)
            mapped.append(
                MappedArgument(
                    expr=arg[0],
                    type=arg[1],
                    argument=param,
                )
            )

        kw_params.update({arg.name: arg for arg in mixed_params})
        for name, arg in keywords.items():
            param: Function.Argument
            if name not in kw_params:
                if name in set_args:
                    self.error(
                        arg[0].location, f"Multiple values for argument '{name}'"
                    )
                else:
                    self.error(arg[0].location, f"Unknown keyword argument '{name}'")
                continue
            param = kw_params.pop(name)
            if name in required_positional:
                required_positional.remove(name)
            if name in required_keyword:
                required_keyword.remove(name)
            set_args.add(name)
            mapped.append(
                MappedArgument(
                    expr=arg[0],
                    type=arg[1],
                    argument=param,
                )
            )

        def join_args(args: list[str]) -> str:
            args = list(map(lambda a: f"'{a}'", args))
            if len(args) == 0:
                return ""
            if len(args) == 1:
                return args[0]
            return ", ".join(args[:-1]) + " and " + args[-1]

        if len(required_positional) != 0:
            plural: str = "" if len(required_positional) == 1 else "s"
            args: str = join_args(required_positional)
            self.error(
                call.location,
                f"Missing required positional argument{plural}: {args}",
            )

        if len(required_keyword) != 0:
            plural: str = "" if len(required_keyword) == 1 else "s"
            args: str = join_args(required_keyword)
            self.error(
                call.location,
                f"Missing required keyword argument{plural}: {args}",
            )

        return mapped
