import ast
import logging
from dataclasses import dataclass
from typing import Optional

import midas.ast.python as p
from midas.ast.location import Location
from midas.checker.environment import Environment
from midas.checker.operators import COMPARATOR_METHODS, OPERATOR_METHODS
from midas.checker.registry import TypesRegistry
from midas.checker.reporter import FileReporter, Reporter
from midas.checker.resolver import Resolver
from midas.checker.types import (
    Function,
    Type,
    UnitType,
    UnknownType,
)
from midas.parser.python import PythonParser


class ReturnException(Exception):
    pass


@dataclass(frozen=True, kw_only=True)
class MappedArgument:
    expr: p.Expr
    type: Type
    argument: Function.Argument


class PythonTyper(
    p.Stmt.Visitor[None],
    p.Expr.Visitor[Type],
    p.MidasType.Visitor[Type],
):
    """A type checker which can use custom type definitions"""

    def __init__(
        self,
        types: TypesRegistry,
        reporter: Reporter,
    ):
        self.logger: logging.Logger = logging.getLogger("PythonTyper")
        self.reporter: FileReporter = reporter.for_file(None)
        self.types: TypesRegistry = types
        self.global_env: Environment = Environment()
        self.env: Environment = self.global_env
        self.locals: dict[p.Expr, int] = {}
        self.judgements: list[tuple[p.Expr, Type]] = []

    def process(self, source: str, path: Optional[str]):
        self.reporter = self.reporter.for_file(path)

        tree: ast.Module = ast.parse(source, filename=path or "<unknown>")
        parser = PythonParser()
        stmts: list[p.Stmt] = parser.parse_module(tree)
        resolver = Resolver()
        resolver.resolve(*stmts)

        self.env = self.global_env
        self.locals = resolver.locals
        self.judgements = []

        self.check(stmts)

    def type_of(self, expr: p.Expr) -> Type:
        """Evaluate the type of an expression

        Args:
            expr (p.Expr): the expression to evaluate

        Returns:
            Type: the type of the given expression
        """
        type: Type = expr.accept(self)
        self.judgements.append((expr, type))
        return type

    def process_block(self, block: list[p.Stmt], env: Environment) -> bool:
        """Evaluate a sequence of statements

        Args:
            block (list[p.Stmt]): the statements to evaluate
            env (Environment): the environment in which to evaluate

        Returns:
            bool: whether a return statement is present in the block
        """
        previous_env: Environment = self.env
        self.env = env
        returned: bool = False
        for i, stmt in enumerate(block):
            try:
                stmt.accept(self)
            except ReturnException:
                returned = True
                if i < len(block) - 1:
                    self.reporter.warning(
                        block[i + 1].location, "Unreachable statement"
                    )
                break
        self.env = previous_env
        return returned

    def check(self, statements: list[p.Stmt]) -> None:
        """Type check a sequence of statements and returns diagnostics

        Args:
            statements (list[p.Stmt]): the statements to evaluate and check
        """
        for stmt in statements:
            stmt.accept(self)

        self.logger.debug(f"Final environment: {self.env.flat_dict()}")

    def look_up_variable(self, name: str, expr: p.Expr) -> Optional[Type]:
        """Look up a variable in the environment it was declared

        Args:
            name (str): the name of the variable
            expr (p.Expr): the variable expression, used to lookup the scope distance

        Returns:
            Optional[Type]: the type of the variable, or None if it was not found
        """
        distance: Optional[int] = self.locals.get(expr)
        if distance is not None:
            return self.env.get_at(distance, name)
        return self.global_env.get(name)

    def is_subtype(self, type1: Type, type2: Type) -> bool:
        return self.types.is_subtype(type1, type2)

    def visit_expression_stmt(self, stmt: p.ExpressionStmt) -> None:
        self.type_of(stmt.expr)

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

        pos: int = 0
        for arg in stmt.posonlyargs:
            pos_args.append(
                Function.Argument(
                    pos=pos,
                    name=arg.name,
                    type=eval_arg_type(arg),
                    required=arg.default is None,
                )
            )
            pos += 1
        for arg in stmt.args:
            args.append(
                Function.Argument(
                    pos=pos,
                    name=arg.name,
                    type=eval_arg_type(arg),
                    required=arg.default is None,
                )
            )
            pos += 1
        for arg in stmt.kwonlyargs:
            kw_args.append(
                Function.Argument(
                    pos=pos,  # not relevant
                    name=arg.name,
                    type=eval_arg_type(arg),
                    required=arg.default is None,
                )
            )
            pos += 1

        for arg in pos_args + args + kw_args:
            env.define(arg.name, arg.type)

        returns_hint: Optional[Type] = None
        if stmt.returns is not None:
            returns_hint = stmt.returns.accept(self)
            # Early define to handle simple fully-typed recursion
            inside_function: Function = Function(
                pos_args=pos_args,
                args=args,
                kw_args=kw_args,
                returns=returns_hint,
            )
            self.env.define(stmt.name, inside_function)

        returned: bool = self.process_block(stmt.body, env)
        inferred_return: Type = UnknownType()
        if not returned:
            env.return_types.append(UnitType())
        return_types: list[Type] = self.types.reduce_types(env.return_types)
        if len(return_types) == 1:
            inferred_return = return_types[0]
        elif len(return_types) > 1:
            self.reporter.error(
                stmt.location,
                f"Mixed return types: {return_types}",
            )

        returns: Type = UnknownType()
        if returns_hint is not None:
            assert stmt.returns is not None
            returns = returns_hint
            if returns != inferred_return:
                self.reporter.error(
                    stmt.returns.location,
                    f"Return type mismatch, annotated {returns} but returns {inferred_return}",
                )
        else:
            returns = inferred_return

        # TODO: handle *args and **kwargs sinks
        function: Function = Function(
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
        value_type: Type = self.type_of(stmt.value)
        for target in stmt.targets:
            self._assign(stmt.location, target, value_type)

    def _assign(self, location: Location, target: p.Expr, value_type: Type):
        match target:
            case p.VariableExpr():
                self._assign_var(location, target, value_type)

            case p.GetExpr(object=object, name=name):
                self._assign_attr(location, object, name, value_type)

            case _:
                if not isinstance(target, p.VariableExpr):
                    self.logger.warning(f"Unsupported assignment to {target}")
                    self.reporter.warning(
                        target.location, f"Unsupported assignment to {target}"
                    )

    def _assign_var(self, location: Location, target: p.VariableExpr, value_type: Type):
        name: str = target.name
        var_type: Optional[Type] = self.look_up_variable(name, target)

        if var_type is None:
            self.env.define(name, value_type)
        else:
            # S <: T
            # Γ, x: T   v: S
            # x = v
            if not self.is_subtype(value_type, var_type):
                self.reporter.error(
                    location,
                    f"Cannot assign {value_type} to variable '{name}' of type {var_type}",
                )

    def _assign_attr(
        self, location: Location, object: p.Expr, name: str, value_type: Type
    ):
        object_type: Type = self.type_of(object)
        member: Optional[Type] = self.types.lookup_member(object_type, name)
        if member is None:
            self.reporter.error(location, f"Unknown member '{name}' of {object_type}")
            return
        self.logger.debug(f"Member '{name}' of {object_type} has type {member}")
        if not self.is_subtype(value_type, member):
            self.reporter.error(
                location,
                f"Cannot assign {value_type} to member '{object_type}.{name}' of type {member}",
            )

    def visit_return_stmt(self, stmt: p.ReturnStmt) -> None:
        type: Type = stmt.value.accept(self) if stmt.value is not None else UnitType()
        self.env.return_types.append(type)
        raise ReturnException()

    def visit_if_stmt(self, stmt: p.IfStmt) -> None:
        # Not evaluated in sub-environment because assignments in the test leak out of the if
        # For example:
        # if (m := 1 + 1) < 2:
        #     ...
        # print(m)  # <- m is still defined
        test_type: Type = stmt.test.accept(self)

        # TODO Allow subtypes or any type
        if test_type != self.types.get_type("bool"):
            self.reporter.error(
                stmt.test.location, f"If test must be a boolean, got {test_type}"
            )

        env: Environment = Environment(self.env)
        body_returned: bool = self.process_block(stmt.body, env)
        else_returned: bool = self.process_block(stmt.orelse, env)
        self.env.return_types.extend(env.return_types)
        if body_returned and else_returned:
            raise ReturnException()

    def visit_binary_expr(self, expr: p.BinaryExpr) -> Type:
        method: Optional[str] = OPERATOR_METHODS.get(expr.operator.__class__)
        if method is None:
            self.logger.warning(f"Unsupported operator {expr.operator}")
            self.reporter.warning(
                expr.location, f"Unsupported operator {expr.operator}"
            )
            return UnknownType()
        left: Type = self.type_of(expr.left)
        right: Type = self.type_of(expr.right)

        operation: Optional[Type] = self.types.lookup_member(left, method)
        if operation is None:
            self.reporter.error(
                expr.location,
                f"Undefined operation {method} between {left} and {right}",
            )
            return UnknownType()

        match operation:
            case Function() as function:
                if not self._is_binary_function(function):
                    self.reporter.error(
                        expr.location,
                        f"Wrong definition of binary operation. Expected function with 1 positional-only parameters, got {function}",
                    )
                    return UnknownType()

                rhs: Function.Argument = function.pos_args[0]
                if not self.is_subtype(right, rhs.type):
                    self.reporter.error(
                        expr.location,
                        f"Wrong type for right-hand side, expected {rhs.type}, got {right}",
                    )
                    return UnknownType()
                return function.returns
            case _:
                self.reporter.warning(
                    expr.location, f"Unsupported operation {operation}"
                )
                return UnknownType()

    def visit_compare_expr(self, expr: p.CompareExpr) -> Type:
        method: Optional[str] = COMPARATOR_METHODS.get(expr.operator.__class__)
        if method is None:
            self.logger.warning(f"Unsupported operator {expr.operator}")
            self.reporter.warning(
                expr.location, f"Unsupported operator {expr.operator}"
            )
            return UnknownType()
        left: Type = self.type_of(expr.left)
        right: Type = self.type_of(expr.right)

        result: Optional[Type] = self.types.get_operation_result(left, method, right)
        if result is None:
            self.reporter.error(
                expr.location,
                f"Undefined operation {method} between {left} and {right}",
            )
            return UnknownType()
        return result

    def visit_unary_expr(self, expr: p.UnaryExpr) -> Type: ...

    def visit_call_expr(self, expr: p.CallExpr) -> Type:
        callee: Type = self.type_of(expr.callee)
        if not isinstance(callee, Function):
            self.reporter.error(expr.callee.location, "Callee is not a function")
            return UnknownType()
        function: Function = callee
        mapped: list[MappedArgument] = self.map_call_arguments(function, expr)
        for arg in mapped:
            if not self.is_subtype(arg.type, arg.argument.type):
                self.reporter.error(
                    arg.expr.location,
                    f"Wrong type for argument '{arg.argument.name}', expected {arg.argument.type}, got {arg.type}",
                )
        return function.returns

    def visit_get_expr(self, expr: p.GetExpr) -> Type:
        object: Type = self.type_of(expr.object)
        member: Optional[Type] = self.types.lookup_member(object, expr.name)
        if member is None:
            self.reporter.error(
                expr.location, f"Unknown member '{expr.name}' of {object}"
            )
            return UnknownType()
        self.logger.debug(f"Member '{expr.name}' of {object} has type {member}")
        return member

    def visit_literal_expr(self, expr: p.LiteralExpr) -> Type:
        match expr.value:
            case bool():  # Must be before int
                return self.types.get_type("bool")
            case int():
                return self.types.get_type("int")
            case float():
                return self.types.get_type("float")
            case str():
                return self.types.get_type("str")
            case _:
                self.reporter.warning(expr.location, f"Unknown literal {expr}")
                return UnknownType()

    def visit_variable_expr(self, expr: p.VariableExpr) -> Type:
        type: Optional[Type] = self.look_up_variable(expr.name, expr)
        if type is None:
            self.logger.debug(f"Unknown variable {expr.name} in {self.env.flat_dict()}")
            self.reporter.warning(expr.location, "Unknown variable")
        return type or UnknownType()

    def visit_logical_expr(self, expr: p.LogicalExpr) -> Type:
        left: Type = expr.left.accept(self)
        right: Type = expr.right.accept(self)

        if self.is_subtype(left, right):
            return right
        if self.is_subtype(right, left):
            return left

        self.reporter.error(
            expr.location,
            f"Incompatible operand types, {left=} and {right=}",
        )
        return UnknownType()

    def visit_cast_expr(self, expr: p.CastExpr) -> Type:
        return expr.type.accept(self)

    def visit_ternary_expr(self, expr: p.TernaryExpr) -> Type:
        test_type: Type = expr.test.accept(self)

        # TODO Allow subtypes or any type
        if test_type != self.types.get_type("bool"):
            self.reporter.error(
                expr.test.location, f"If test must be a boolean, got {test_type}"
            )

        true_type: Type = expr.if_true.accept(self)
        false_type: Type = expr.if_false.accept(self)
        if self.is_subtype(true_type, false_type):
            return false_type
        if self.is_subtype(false_type, true_type):
            return true_type

        self.reporter.error(
            expr.location,
            f"Incompatible types in ternary if branches: true={true_type} and false={false_type}",
        )
        return UnknownType()

    def visit_list_expr(self, expr: p.ListExpr) -> Type:
        list_type: Type = self.types.get_type("list")
        item_types: list[Type] = [self.type_of(item) for item in expr.items]
        item_types = self.types.reduce_types(item_types)

        if len(item_types) == 0:
            return list_type

        if len(item_types) == 1:
            item_type: Type = item_types[0]
            return self.types.apply_generic(list_type, [item_type])
        self.reporter.error(
            expr.location,
            f"Heterogeneous list items: {item_types}",
        )
        return self.types.apply_generic(list_type, [UnknownType()])

    def visit_base_type(self, node: p.BaseType) -> Type:
        base: Type = self.types.get_type(node.base)
        if node.param is not None:
            param: Type = node.param.accept(self)
            return self.types.apply_generic(base, [param])
        return base

    def visit_constraint_type(self, node: p.ConstraintType) -> Type: ...

    def visit_frame_column(self, node: p.FrameColumn) -> Type: ...

    def visit_frame_type(self, node: p.FrameType) -> Type: ...

    def map_call_arguments(
        self, function: Function, call: p.CallExpr
    ) -> list[MappedArgument]:
        """Map call arguments to function parameters as defined in its signature

        This method maps positional-only, keyword-only and mixed parameter definitions
        with the arguments passed at the call site

        Any mismatched, missing or unexpected argument is reported as a diagnostic

        Args:
            function (Function): the function definition
            call (p.CallExpr): the call expression

        Returns:
            list[MappedArgument]: the list of mapped arguments
        """
        positional: list[tuple[p.Expr, Type]] = [
            (arg, self.type_of(arg)) for arg in call.arguments
        ]
        keywords: dict[str, tuple[p.Expr, Type]] = {
            name: (arg, self.type_of(arg)) for name, arg in call.keywords.items()
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
                self.reporter.error(arg[0].location, "Too many positional arguments")
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
                    self.reporter.error(
                        arg[0].location, f"Multiple values for argument '{name}'"
                    )
                else:
                    self.reporter.error(
                        arg[0].location, f"Unknown keyword argument '{name}'"
                    )
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
            self.reporter.error(
                call.location,
                f"Missing required positional argument{plural}: {args}",
            )

        if len(required_keyword) != 0:
            plural: str = "" if len(required_keyword) == 1 else "s"
            args: str = join_args(required_keyword)
            self.reporter.error(
                call.location,
                f"Missing required keyword argument{plural}: {args}",
            )

        return mapped

    def _is_binary_function(self, function: Function) -> bool:
        if len(function.pos_args) != 1:
            return False
        if len(function.args) != 0:
            return False
        if len(function.kw_args) != 0:
            return False
        return True
