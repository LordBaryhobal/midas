import ast
import logging
from dataclasses import dataclass
from typing import Optional

import midas.ast.python as p
from midas.ast.location import Location
from midas.checker.environment import Environment
from midas.checker.operators import COMPARATOR_METHODS, OPERATOR_METHODS, UNARY_METHODS
from midas.checker.preamble import Preamble
from midas.checker.registry import TypesRegistry
from midas.checker.reporter import FileReporter, Reporter
from midas.checker.resolver import Resolver
from midas.checker.types import (
    AppliedType,
    Function,
    OverloadedFunction,
    Type,
    UnitType,
    UnknownType,
    unfold_type,
)
from midas.parser.python import PythonParser
from midas.utils import TypedAST

TypedExpr = tuple[p.Expr, Type]


class ReturnException(Exception):
    pass


@dataclass(frozen=True, kw_only=True)
class MappedArgument:
    expr: p.Expr
    type: Type
    argument: Function.Argument


@dataclass(frozen=True, kw_only=True)
class OverloadCandidate:
    function: Function
    mapped: list[MappedArgument]


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
        self.global_env: Environment = Preamble(self.types)
        self.env: Environment = self.global_env
        self.locals: dict[p.Expr, int] = {}
        self.judgements: list[tuple[p.Expr, Type]] = []

    def process(self, source: str, path: Optional[str]) -> TypedAST:
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

        return TypedAST(stmts=stmts, judgements=self.judgements)

    def judge(self, expr: p.Expr, type: Type):
        """Record a typing judgement

        Args:
            expr (p.Expr): the judged expression
            type (Type): the type of the expression
        """
        self.judgements.append((expr, type))

    def compute_type(self, expr: p.Expr) -> Type:
        """Evaluate the type of an expression

        Args:
            expr (p.Expr): the expression to type

        Returns:
            Type: the type of the given expression
        """
        return expr.accept(self)

    def type_of(self, expr: p.Expr) -> Type:
        """Evaluate the type of an expression and record the judgement

        Args:
            expr (p.Expr): the expression to evaluate

        Returns:
            Type: the type of the given expression
        """
        type: Type = self.compute_type(expr)
        self.judge(expr, type)
        return type

    def resolve_type_expr(self, expr: p.MidasType) -> Type:
        return expr.accept(self)

    def process_stmt(self, stmt: p.Stmt) -> None:
        stmt.accept(self)

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
                self.process_stmt(stmt)
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
            self.process_stmt(stmt)

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
                return self.resolve_type_expr(arg.type)
            if arg.default is not None:
                return self.type_of(arg.default)
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
            returns_hint = self.resolve_type_expr(stmt.returns)
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
            if not self.is_subtype(inferred_return, returns):
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
        type: Type = self.resolve_type_expr(stmt.type)
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
        type: Type = self.type_of(stmt.value) if stmt.value is not None else UnitType()
        self.env.return_types.append(type)
        raise ReturnException()

    def visit_if_stmt(self, stmt: p.IfStmt) -> None:
        # Not evaluated in sub-environment because assignments in the test leak out of the if
        # For example:
        # if (m := 1 + 1) < 2:
        #     ...
        # print(m)  # <- m is still defined
        test_type: Type = self.type_of(stmt.test)

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

    def visit_pass(self, stmt: p.Pass) -> None:
        pass

    def visit_for_stmt(self, stmt: p.ForStmt) -> None:
        item_type: Optional[Type] = self._get_iterator_type(stmt.iterator)
        if item_type is None:
            iterator_type: Type = self.compute_type(stmt.iterator)
            self.reporter.error(
                stmt.iterator.location, f"{iterator_type} is not iterable"
            )
            item_type = UnknownType()

        self._assign(stmt.location, stmt.target, item_type)
        self.judge(stmt.target, item_type)
        env: Environment = Environment(self.env)
        body_returned: bool = self.process_block(stmt.body, env)
        if body_returned:
            raise ReturnException()

    def visit_raw_stmt(self, stmt: p.RawStmt) -> None:
        pass

    def visit_binary_expr(self, expr: p.BinaryExpr) -> Type:
        method: Optional[str] = OPERATOR_METHODS.get(expr.operator.__class__)
        if method is None:
            self.logger.warning(f"Unsupported operator {expr.operator}")
            self.reporter.warning(
                expr.location, f"Unsupported operator {expr.operator}"
            )
            return UnknownType()

        return self._visit_binary_expr(expr.location, expr.left, expr.right, method)

    def visit_compare_expr(self, expr: p.CompareExpr) -> Type:
        method: Optional[str] = COMPARATOR_METHODS.get(expr.operator.__class__)
        if method is None:
            self.logger.warning(f"Unsupported operator {expr.operator}")
            self.reporter.warning(
                expr.location, f"Unsupported operator {expr.operator}"
            )
            return UnknownType()

        return self._visit_binary_expr(expr.location, expr.left, expr.right, method)

    def _visit_binary_expr(
        self, location: Location, left_expr: p.Expr, right_expr: p.Expr, method: str
    ) -> Type:
        left: Type = self.type_of(left_expr)
        right: Type = self.type_of(right_expr)

        operation: Optional[Type] = self.types.lookup_member(left, method)
        if operation is None:
            self.reporter.error(
                location,
                f"Undefined operation {method} between {left} and {right}",
            )
            return UnknownType()

        result: Optional[Type] = self._get_call_result(
            location,
            operation,
            [(right_expr, right)],
            {},
        )
        return result or UnknownType()

    def visit_unary_expr(self, expr: p.UnaryExpr) -> Type:
        method: Optional[str] = UNARY_METHODS.get(expr.operator.__class__)
        if method is None:
            self.logger.warning(f"Unsupported operator {expr.operator}")
            self.reporter.warning(
                expr.location, f"Unsupported operator {expr.operator}"
            )
            return UnknownType()

        operand: Type = self.type_of(expr.right)
        operation: Optional[Type] = self.types.lookup_member(operand, method)
        if operation is None:
            self.reporter.error(
                expr.location,
                f"Undefined operation {method} for {operand}",
            )
            return UnknownType()

        result: Optional[Type] = self._get_call_result(
            expr.location,
            operation,
            [],
            {},
        )
        return result or UnknownType()

    def visit_call_expr(self, expr: p.CallExpr) -> Type:
        callee: Type = self.type_of(expr.callee)
        positional: list[TypedExpr] = [
            (arg, self.type_of(arg)) for arg in expr.arguments
        ]
        keywords: dict[str, TypedExpr] = {
            name: (arg, self.type_of(arg)) for name, arg in expr.keywords.items()
        }
        return (
            self._get_call_result(
                location=expr.location,
                callee=callee,
                positional=positional,
                keywords=keywords,
            )
            or UnknownType()
        )

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
        left: Type = self.type_of(expr.left)
        right: Type = self.type_of(expr.right)

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
        return self.resolve_type_expr(expr.type)

    def visit_ternary_expr(self, expr: p.TernaryExpr) -> Type:
        test_type: Type = self.type_of(expr.test)

        # TODO Allow subtypes or any type
        if test_type != self.types.get_type("bool"):
            self.reporter.error(
                expr.test.location, f"If test must be a boolean, got {test_type}"
            )

        true_type: Type = self.type_of(expr.if_true)
        false_type: Type = self.type_of(expr.if_false)
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

    def visit_dict_expr(self, expr: p.DictExpr) -> Type:
        dict_type: Type = self.types.get_type("dict")

        key_types: list[Type] = []
        value_types: list[Type] = []
        for key, value in zip(expr.keys, expr.values):
            if key is None:
                self.reporter.warning(
                    value.location, "Dictionary unpacking not supported"
                )
                continue
            key_types.append(self.type_of(key))
            value_types.append(self.type_of(value))

        key_types = self.types.reduce_types(key_types)
        value_types = self.types.reduce_types(value_types)

        if len(key_types) == 0 or len(value_types) == 0:
            return dict_type

        key_type: Type = UnknownType()
        value_type: Type = UnknownType()

        if len(key_types) == 1:
            key_type = key_types[0]
        else:
            self.reporter.error(
                expr.location,
                f"Heterogeneous dict keys: {key_types}",
            )

        if len(value_types) == 1:
            value_type = value_types[0]
        else:
            self.reporter.error(
                expr.location,
                f"Heterogeneous dict values: {value_types}",
            )
        return self.types.apply_generic(dict_type, [key_type, value_type])

    def visit_subscript_expr(self, expr: p.SubscriptExpr) -> Type:
        object: Type = self.type_of(expr.object)
        operation: Optional[Type] = self.types.lookup_member(object, "__getitem__")
        if operation is None:
            self.reporter.error(
                expr.location,
                f"Undefined method __getitem__ on {object}",
            )
            return UnknownType()

        index: Type = self.type_of(expr.index)
        return (
            self._get_call_result(expr.location, operation, [(expr.index, index)], {})
            or UnknownType()
        )

    def visit_slice_expr(self, expr: p.SliceExpr) -> Type:
        return self.types.get_type("slice")

    def visit_raw_expr(self, expr: p.RawExpr) -> Type:
        return UnknownType()

    def visit_base_type(self, node: p.BaseType) -> Type:
        base: Type
        try:
            base = self.types.get_type(node.base)
        except NameError:
            self.reporter.warning(node.location, f"Unknown type '{node.base}'")
            return UnknownType()

        if node.param is not None:
            param: Type = self.resolve_type_expr(node.param)
            return self.types.apply_generic(base, [param])
        return base

    def visit_constraint_type(self, node: p.ConstraintType) -> Type:
        self.reporter.warning(node.location, "ConstraintType not yet supported")
        return UnknownType()

    def visit_frame_column(self, node: p.FrameColumn) -> Type:
        self.reporter.warning(node.location, "FrameColumn not yet supported")
        return UnknownType()

    def visit_frame_type(self, node: p.FrameType) -> Type:
        self.reporter.warning(node.location, "FrameType not yet supported")
        return UnknownType()

    def _get_call_result(
        self,
        location: Location,
        callee: Type,
        positional: list[TypedExpr],
        keywords: dict[str, TypedExpr],
        report_errors: bool = True,
    ) -> Optional[Type]:
        """Get the result type of a function call

        If the function has overloads, the function will try to resolve the
        appropriate signature.
        Argument types are matched to the defined parameters.
        The function doesn't take the raw expression as a parameter to accommodate
        for desugared calls such as for operators.

        Args:
            location (Location): the call location
            callee (Type): the called function
            positional (list[TypedExpr]): the list positional arguments
            keywords (dict[str, TypedExpr]): the map of keyword arguments
            report_errors (bool, optional): whether type errors should be reported as diagnostics. Defaults to True.

        Returns:
            Type: the return type of the call, or `None` if either
            the call is invalid or no overload matched the arguments uniquely
        """
        match callee:
            case Function() as function:
                valid: bool
                mapped: list[MappedArgument]
                valid, mapped = self.map_call_arguments(
                    function, location, positional, keywords
                )
                valid = valid and self._are_arguments_valid(mapped, report_errors)
                if not valid:
                    return None
                return function.returns

            case OverloadedFunction(overloads=overloads):
                function = self._match_overload(
                    overloads, location, positional, keywords, report_errors
                )
                if function is None:
                    return None
                return function.returns

            case AppliedType(body=body):
                return self._get_call_result(
                    location, body, positional, keywords, report_errors
                )

            case UnknownType():
                return UnknownType()

            case _:
                if report_errors:
                    self.reporter.error(location, f"{callee} is not callable")
                return None

    def _are_arguments_valid(
        self,
        arguments: list[MappedArgument],
        report_errors: bool = True,
    ) -> bool:
        """Check whether the passed argument types correspond to their matched parameter definitions

        Args:
            arguments (list[MappedArgument]): the list of argument/parameter pairs
            report_errors (bool, optional): whether type errors should be reported as diagnostics. Defaults to True.

        Returns:
            bool: True if all arguments fit the matching parameter definitions, False otherwise
        """
        valid: bool = True
        for arg in arguments:
            if not self.is_subtype(arg.type, arg.argument.type):
                if report_errors:
                    self.reporter.error(
                        arg.expr.location,
                        f"Wrong type for argument '{arg.argument.name}', expected {arg.argument.type}, got {arg.type}",
                    )
                valid = False
        return valid

    def _match_overload(
        self,
        overloads: list[Type],
        location: Location,
        positional: list[TypedExpr],
        keywords: dict[str, TypedExpr],
        report_errors: bool = True,
    ) -> Optional[Function]:
        """Try and resolve the appropriate overload for the given arguments

        Args:
            overloads (list[Type]): the list of possible overloads
            location (Location): the call location
            positional (list[TypedExpr]): the list of positional arguments
            keywords (dict[str, TypedExpr]): the map of keywords arguments
            report_errors (bool, optional): whether type errors should be reported as diagnostics. Defaults to True.

        Returns:
            Optional[Function]: the resolved function signature if it can be
            determined unambiguously, or `None`.
        """
        candidates: list[OverloadCandidate] = []
        for overload in overloads:
            function: Type = unfold_type(overload)
            if not isinstance(function, Function):
                if report_errors:
                    self.logger.error(
                        f"Overload is not a function: {overload} is {function}"
                    )
                continue
            valid, mapped = self.map_call_arguments(
                function=function,
                location=location,
                positional=positional,
                keywords=keywords,
                report_errors=False,
            )
            if valid and self._are_arguments_valid(mapped, report_errors=False):
                candidates.append(
                    OverloadCandidate(
                        function=function,
                        mapped=mapped,
                    )
                )

        pos_types: str = ", ".join(str(type) for _, type in positional)
        kw_types: str = ", ".join(
            f"{name}: {type}" for name, (_, type) in keywords.items()
        )
        for_args: str = f"for arguments pos=[{pos_types}] and kw={{{kw_types}}}"

        n_candidates: int = len(candidates)

        # Exactly 1 match -> return it
        if n_candidates == 1:
            return candidates[0].function

        # No match -> invalid call
        if n_candidates == 0:
            overloads_str: str = ", ".join(map(str, overloads))
            if report_errors:
                self.reporter.error(
                    location,
                    f"No matching overload in [{overloads_str}] {for_args}",
                )
            return None

        # Multiple matches -> see if one <: all others (more specific)
        for i1, c1 in enumerate(candidates):
            mapped1: list[MappedArgument] = c1.mapped
            best_match: bool = True
            for i2, c2 in enumerate(candidates):
                if i1 == i2:
                    continue
                mapped2: list[MappedArgument] = c2.mapped
                if not self._are_mapped_subtypes(mapped1, mapped2):
                    best_match = False
                    break
                self.logger.debug(f"{c1.function} is a full overload of {c2.function}")
            if best_match:
                return c1.function

        candidates_str: str = ", ".join(
            str(candidate.function) for candidate in candidates
        )
        if report_errors:
            self.reporter.error(
                location,
                f"Multiple matching overloads {for_args}: {candidates_str}",
            )
        return None

    def map_call_arguments(
        self,
        function: Function,
        location: Location,
        positional: list[TypedExpr],
        keywords: dict[str, TypedExpr],
        report_errors: bool = True,
    ) -> tuple[bool, list[MappedArgument]]:
        """Map call arguments to a function's parameters as defined in its signature

        This method maps positional-only, keyword-only and mixed parameter definitions
        with the arguments passed at the call site

        Any mismatched, missing or unexpected argument is reported as a diagnostic,
        unless `report_errors` is set to `False`

        Args:
            function (Function): the function definition
            location (Location): the call location
            positional (list[TypedExpr]): the list of positional arguments
            keywords (dict[str, TypedExpr]): the map of keyword arguments
            report_errors (bool, optional): whether type errors should be reported as diagnostics. Defaults to True.

        Returns:
            tuple[bool, list[MappedArgument]]: a boolean reporting whether
            the call is valid and the list of mapped arguments
        """
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

        valid_call: bool = True

        # TODO: handle *args and **kwargs sinks
        for arg in positional:
            param: Function.Argument
            if len(pos_params) != 0:
                param = pos_params.pop(0)
            elif len(mixed_params) != 0:
                param = mixed_params.pop(0)
            else:
                if report_errors:
                    self.reporter.error(
                        arg[0].location, "Too many positional arguments"
                    )
                valid_call = False
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
                if report_errors:
                    if name in set_args:
                        self.reporter.error(
                            arg[0].location, f"Multiple values for argument '{name}'"
                        )
                    else:
                        self.reporter.error(
                            arg[0].location, f"Unknown keyword argument '{name}'"
                        )
                valid_call = False
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
            if report_errors:
                self.reporter.error(
                    location,
                    f"Missing required positional argument{plural}: {args}",
                )
            valid_call = False

        if len(required_keyword) != 0:
            plural: str = "" if len(required_keyword) == 1 else "s"
            args: str = join_args(required_keyword)
            if report_errors:
                self.reporter.error(
                    location,
                    f"Missing required keyword argument{plural}: {args}",
                )
            valid_call = False

        return valid_call, mapped

    def _are_mapped_subtypes(
        self, mapped1: list[MappedArgument], mapped2: list[MappedArgument]
    ) -> bool:
        """Check whether the given argument mappings are subtype/supertype of one another

        This function checks whether the argument mappings `mapped1` are subtypes
        of `mapped2`. If any of the parameter type in `mapped1` is not a subtype
        of the corresponding parameter in `mapped2`, `False` is returned.

        This is used to check whether a given overload is
        a more specific function/ a subtype of another.

        Args:
            mapped1 (list[MappedArgument]): the first argument mappings (subtype)
            mapped2 (list[MappedArgument]): the second argument mappings (supertype)

        Returns:
            bool: `True` if `mapped1` is a subtype of `mapped2`, `False` otherwise
        """
        by_expr: dict[p.Expr, Type] = {}
        for arg in mapped1:
            by_expr[arg.expr] = arg.argument.type

        for arg in mapped2:
            type2: Type = arg.argument.type
            type1: Type = by_expr[arg.expr]
            if not self.is_subtype(type1, type2):
                return False
        return True

    def _get_iterator_type(self, expr: p.Expr) -> Optional[Type]:
        # TODO: lookup __iter__
        type: Type = self.type_of(expr)
        getitem: Optional[Type] = self.types.lookup_member(type, "__getitem__")
        if getitem is None:
            return None

        index: p.Expr = p.LiteralExpr(location=expr.location, value=0)
        index_type: Type = self.compute_type(index)
        result: Optional[Type] = self._get_call_result(
            location=expr.location,
            callee=getitem,
            positional=[(index, index_type)],
            keywords={},
            report_errors=False,
        )
        return result
