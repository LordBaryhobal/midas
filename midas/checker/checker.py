import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import midas.ast.midas as m
import midas.ast.python as p
from midas.ast.location import Location
from midas.checker.builtins import BUILTIN_SUBTYPES
from midas.checker.diagnostic import Diagnostic, DiagnosticType
from midas.checker.environment import Environment
from midas.checker.operators import COMPARATOR_METHODS, OPERATOR_METHODS
from midas.checker.types import (
    AliasType,
    BaseType,
    ComplexType,
    Function,
    Operation,
    Type,
    UnitType,
    UnknownType,
    unfold_type,
)
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
    """A type checker which can use custom type definitions"""

    def __init__(
        self,
        locals: dict[p.Expr, int],
        source_path: Path,
        types_paths: list[Path],
    ):
        self.logger: logging.Logger = logging.getLogger("Checker")
        self.source_path: Path = source_path
        self.types_paths: list[Path] = types_paths
        self.ctx: MidasResolver = MidasResolver()
        self.global_env: Environment = Environment()
        self.env: Environment = self.global_env
        self.locals: dict[p.Expr, int] = locals
        self.diagnostics: list[Diagnostic] = []
        self.judgements: list[tuple[p.Expr, Type]] = []

    def diagnostic(self, type: DiagnosticType, location: Location, message: str):
        self.diagnostics.append(
            Diagnostic(
                file_path=self.source_path,
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
                    self.warning(block[i + 1].location, "Unreachable statement")
                break
        self.env = previous_env
        return returned

    def check(self, statements: list[p.Stmt]) -> list[Diagnostic]:
        """Type check a sequence of statements and returns diagnostics

        Args:
            statements (list[p.Stmt]): the statements to evaluate and check

        Returns:
            list[Diagnostic]: the list of diagnostics (errors, warning, etc.)
        """
        self.diagnostics = []

        for path in self.types_paths:
            self.import_midas(path)
        self.logger.debug(f"Midas types: {self.ctx._types}")
        self.logger.debug(f"Midas operations: {self.ctx._operations}")

        for stmt in statements:
            stmt.accept(self)

        self.logger.debug(f"Final environment: {self.env.flat_dict()}")
        return self.diagnostics

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

    def import_midas(self, path: Path) -> None:
        """Import Midas definitions from a path

        Args:
            path (Path): the import path
        """
        self.logger.debug(f"Importing type definitions from {path}")
        lexer: MidasLexer = MidasLexer(path.read_text())
        tokens: list[Token] = lexer.process()
        parser: MidasParser = MidasParser(tokens)
        stmts: list[m.Stmt] = parser.parse()
        self.ctx.resolve(stmts)

    def is_subtype(self, type1: Type, type2: Type) -> bool:
        """Check whether `type1` is a subtype of `type2`

        For more details on the rules checked here, see TAPL Chap. 15-16-17

        Args:
            type1 (Type): the potential subtype
            type2 (Type): the potential supertype

        Returns:
            bool: whether `type1` is a subtype of `type2`
        """

        if type1 == type2:
            return True

        match (type1, type2):
            case (AliasType(type=base1), _):
                return self.is_subtype(base1, type2)

            case (BaseType(name=name1), BaseType(name=name2)):
                return name1 in BUILTIN_SUBTYPES.get(name2, set())

            case (ComplexType(properties=props1), ComplexType(properties=props2)):
                for k, t in props2.items():
                    if k not in props1:
                        return False
                    if not self.is_subtype(props1[k], t):
                        return False
                return True

            case (Function(returns=return1), Function(returns=return2)):
                if not self.is_func_subtype(type1, type2):
                    return False
                if not self.is_subtype(return1, return2):
                    return False
                return True

        return False

    # TODO: verify the logic in here
    def is_func_subtype(self, func1: Function, func2: Function) -> bool:
        """Check whether a function is a subtype of another

        Args:
            func1 (Function): the potential function subtype
            func2 (Function): the potential function supertype

        Returns:
            bool: whether `func1` is a subtype of `func2`
        """
        if not self.is_subtype(func1.returns, func2.returns):
            return False

        pos1: list[Function.Argument] = func1.pos_args
        mixed1: list[Function.Argument] = func1.args
        kw1: dict[str, Function.Argument] = {a.name: a for a in func1.kw_args}
        pos2: list[Function.Argument] = func2.pos_args
        mixed2: list[Function.Argument] = func2.args
        kw2: dict[str, Function.Argument] = {a.name: a for a in func2.kw_args}

        mixed_by_pos: dict[int, Function.Argument] = {arg.pos: arg for arg in mixed2}
        mixed_by_name: dict[str, Function.Argument] = {arg.name: arg for arg in mixed2}

        def is_arg_subtype(sub: Function.Argument, sup: Function.Argument) -> bool:
            if not self.is_subtype(sub.type, sup.type):
                return False
            if not sup.required and sub.required:
                return False
            return True

        for arg1 in pos1:
            arg2: Function.Argument
            if arg1.pos < len(pos2):
                arg2 = pos2[arg1.pos]
            elif arg1.pos in mixed_by_pos:
                arg2 = mixed_by_pos[arg1.pos]
            elif not arg1.required:
                continue
            else:
                return False
            if not is_arg_subtype(arg2, arg1):
                return False

        for name, arg1 in kw1.items():
            arg2: Function.Argument
            if name in kw2:
                arg2 = kw2[name]
            elif name in mixed_by_name:
                arg2 = mixed_by_name[name]
            elif not arg1.required:
                continue
            else:
                return False
            if not is_arg_subtype(arg2, arg1):
                return False

        for arg1 in mixed1:
            pos_arg2: Optional[Function.Argument] = None
            kw_arg2: Optional[Function.Argument] = None
            if arg1.name in kw2:
                kw_arg2 = kw2[arg1.name]
            elif arg1.name in mixed_by_name:
                kw_arg2 = mixed_by_name[arg1.name]
            if arg1.pos < len(pos2):
                pos_arg2 = pos2[arg1.pos]
            elif arg1.pos in mixed_by_pos:
                pos_arg2 = mixed_by_pos[arg1.pos]

            # No match in func2 and arg is required
            if pos_arg2 is None and kw_arg2 is None and arg1.required:
                return False

            # Matching keyword argument
            if kw_arg2 is not None and not is_arg_subtype(kw_arg2, arg1):
                return False

            # Matching positional argument
            if pos_arg2 is not None and not is_arg_subtype(pos_arg2, arg1):
                return False

        mixed_positions: set[int] = {a.pos for a in mixed1}
        mixed_names: set[str] = {a.name for a in mixed1}
        for arg2 in pos2:
            if not arg2.required:
                continue
            if arg2.pos >= len(pos1) and arg2.pos not in mixed_positions:
                return False

        for name, arg2 in kw2.items():
            if not arg2.required:
                continue
            if name not in kw1 and name not in mixed_names:
                return False

        for arg2 in mixed2:
            if arg2.required:
                continue
            pos_match: bool = arg2.pos < len(pos1) or arg2.pos in mixed_positions
            kw_match: bool = arg2.name in kw1 or arg2.name in mixed_names
            if not pos_match or not kw_match:
                return False

        return True

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
                name=stmt.name,
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
        return_types: set[Type] = set(env.return_types)
        if len(return_types) == 1:
            inferred_return = list(return_types)[0]
        elif len(return_types) > 1:
            self.error(
                stmt.location,
                f"Mixed return types: {env.return_types}",
            )

        returns: Type = UnknownType()
        if returns_hint is not None:
            assert stmt.returns is not None
            returns = returns_hint
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
        value_type: Type = self.type_of(stmt.value)
        for target in stmt.targets:
            self._assign(stmt.location, target, value_type)

    def _assign(self, location: Location, target: p.Expr, value_type: Type):
        match target:
            case p.VariableExpr():
                self._assign_var(location, target, value_type)

            case p.GetExpr():
                self._assign_attr(location, target, value_type)

            case _:
                if not isinstance(target, p.VariableExpr):
                    self.logger.warning(f"Unsupported assignment to {target}")
                    self.warning(target.location, f"Unsupported assignment to {target}")

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
                self.error(
                    location,
                    f"Cannot assign {value_type} to {name} of type {var_type}",
                )

    def _assign_attr(self, location: Location, target: p.GetExpr, value_type: Type):
        object: Type = self.type_of(target.object)
        base_object: Type = unfold_type(object)
        match base_object:
            case ComplexType(properties=properties):
                if target.name not in properties:
                    self.error(
                        target.location, f"Unknown property '{target.name} on {object}"
                    )
                    return

                prop_type: Type = properties[target.name]
                if not self.is_subtype(value_type, prop_type):
                    self.error(
                        location,
                        f"Cannot assign {value_type} to property '{target.name}' of type {prop_type} on {object}",
                    )
                    return

            case UnknownType():
                pass

            case _:
                self.error(
                    target.location,
                    f"Cannot assign {value_type} to unknown property '{target.name}' on {object}",
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
        if test_type != self.ctx.get_type("bool"):
            self.error(
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
            self.warning(expr.location, f"Unsupported operator {expr.operator}")
            return UnknownType()
        left: Type = self.type_of(expr.left)
        right: Type = self.type_of(expr.right)

        operations: list[Operation] = self.ctx.get_operations_by_name(method)
        valid_operations: list[Operation] = []
        for op in operations:
            sig: Operation.CallSignature = op.signature
            if self.is_subtype(left, sig.left) and self.is_subtype(right, sig.right):
                valid_operations.append(op)

        if len(valid_operations) == 0:
            self.error(
                expr.location,
                f"Undefined operation {method} between {left} and {right}",
            )
            return UnknownType()
        elif len(valid_operations) == 1:
            self.logger.debug(f"Unique operation {method} between {left} and {right}")
            return valid_operations[0].result

        for i, op1 in enumerate(valid_operations):
            sig1: Operation.CallSignature = op1.signature
            best_match: bool = True
            for j, op2 in enumerate(valid_operations):
                if i == j:
                    continue
                sig2: Operation.CallSignature = op2.signature
                if not self.is_subtype(sig1.left, sig2.left) or not self.is_subtype(
                    sig1.right, sig2.right
                ):
                    best_match = False
                    break
                self.logger.debug(f"{op1} is a full overload of {op2}")
            if best_match:
                return op1.result

        overloads: list[str] = [
            f"({op.signature.left} {op.signature.method} {op.signature.right}) -> {op.result}"
            for op in valid_operations
        ]
        self.error(
            expr.location,
            f"Ambiguous operation {method} between {left} and {right}, multiple matching overloads: {', '.join(overloads)}",
        )
        return UnknownType()

    def visit_compare_expr(self, expr: p.CompareExpr) -> Type:
        method: Optional[str] = COMPARATOR_METHODS.get(expr.operator.__class__)
        if method is None:
            self.logger.warning(f"Unsupported operator {expr.operator}")
            self.warning(expr.location, f"Unsupported operator {expr.operator}")
            return UnknownType()
        left: Type = self.type_of(expr.left)
        right: Type = self.type_of(expr.right)

        result: Optional[Type] = self.ctx.get_operation_result(left, method, right)
        if result is None:
            self.error(
                expr.location,
                f"Undefined operation {method} between {left} and {right}",
            )
            return UnknownType()
        return result

    def visit_unary_expr(self, expr: p.UnaryExpr) -> Type: ...

    def visit_call_expr(self, expr: p.CallExpr) -> Type:
        callee: Type = self.type_of(expr.callee)
        if not isinstance(callee, Function):
            self.error(expr.callee.location, "Callee is not a function")
            return UnknownType()
        function: Function = callee
        mapped: list[MappedArgument] = self.map_call_arguments(function, expr)
        for arg in mapped:
            if not self.is_subtype(arg.type, arg.argument.type):
                self.error(
                    arg.expr.location,
                    f"Wrong type for argument '{arg.argument.name}', expected {arg.argument.type}, got {arg.type}",
                )
        return function.returns

    def visit_get_expr(self, expr: p.GetExpr) -> Type:
        object: Type = self.type_of(expr.object)
        base_object: Type = unfold_type(object)
        match base_object:
            case ComplexType(properties=properties):
                if expr.name not in properties:
                    self.error(
                        expr.location, f"Unknown property '{expr.name} on {object}"
                    )
                    return UnknownType()
                return properties[expr.name]

            case UnknownType():
                return UnknownType()

            case _:
                self.error(
                    expr.location, f"Cannot get property '{expr.name}' on {object}"
                )
                return UnknownType()

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

    def visit_logical_expr(self, expr: p.LogicalExpr) -> Type:
        left: Type = expr.left.accept(self)
        right: Type = expr.right.accept(self)

        if self.is_subtype(left, right):
            return right
        if self.is_subtype(right, left):
            return left

        self.error(
            expr.location,
            f"Incompatible operand types, {left=} and {right=}",
        )
        return UnknownType()

    def visit_cast_expr(self, expr: p.CastExpr) -> Type:
        return expr.type.accept(self)

    def visit_ternary_expr(self, expr: p.TernaryExpr) -> Type:
        test_type: Type = expr.test.accept(self)

        # TODO Allow subtypes or any type
        if test_type != self.ctx.get_type("bool"):
            self.error(
                expr.test.location, f"If test must be a boolean, got {test_type}"
            )

        true_type: Type = expr.if_true.accept(self)
        false_type: Type = expr.if_false.accept(self)
        if self.is_subtype(true_type, false_type):
            return false_type
        if self.is_subtype(false_type, true_type):
            return true_type

        self.error(
            expr.location,
            f"Incompatible types in ternary if branches: true={true_type} and false={false_type}",
        )
        return UnknownType()

    def visit_base_type(self, node: p.BaseType) -> Type:
        return self.ctx.get_type(node.base)

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
