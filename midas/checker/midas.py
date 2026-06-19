import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import midas.ast.midas as m
from midas.ast.location import Location
from midas.checker.builtins import define_builtins
from midas.checker.environment import Environment
from midas.checker.operators import MIDAS_BINARY_METHODS, MIDAS_UNARY_METHODS
from midas.checker.preamble import Preamble
from midas.checker.registry import TypesRegistry
from midas.checker.reporter import FileReporter, Reporter
from midas.checker.types import (
    AliasType,
    AppliedType,
    ComplexType,
    ConstraintType,
    ExtensionType,
    Function,
    GenericType,
    OverloadedFunction,
    Predicate,
    Type,
    TypeVar,
    UnknownType,
    unfold_type,
)
from midas.lexer.midas import MidasLexer
from midas.lexer.token import Token
from midas.parser.midas import MidasParser


@dataclass(frozen=True, kw_only=True)
class TypedParamSpec:
    pos: list[Function.Argument]
    mixed: list[Function.Argument]
    kw: list[Function.Argument]


TypedExpr = tuple[m.Expr, Type]


class ReturnException(Exception):
    pass


@dataclass(frozen=True, kw_only=True)
class MappedArgument:
    expr: m.Expr
    type: Type
    argument: Function.Argument


@dataclass(frozen=True, kw_only=True)
class OverloadCandidate:
    function: Function
    mapped: list[MappedArgument]


class MidasTyper(m.Stmt.Visitor[None], m.Expr.Visitor[Type], m.Type.Visitor[Type]):
    """A resolver which evaluates Midas type definitions and build a registry"""

    def __init__(self, types: TypesRegistry, reporter: Reporter) -> None:
        self.logger: logging.Logger = logging.getLogger("MidasTyper")
        self.reporter: FileReporter = reporter.for_file(None)

        self.types: TypesRegistry = types
        self._local_variables: dict[str, TypeVar] = {}

        self._predicate_params: dict[str, Type] = {}

        self._current_name: Optional[str] = None

        define_builtins(self.types)
        builtins_path: Path = (Path(__file__).parent / "builtins.midas").resolve()
        self.process(builtins_path.read_text(), str(builtins_path))

        self._bool: Type = self.get_type("bool")

        self._preamble: Environment = Preamble(self.types)

    def process(self, source: str, path: Optional[str]):
        self.reporter = self.reporter.for_file(path)
        lexer: MidasLexer = MidasLexer(source)
        tokens: list[Token] = lexer.process()
        parser: MidasParser = MidasParser(tokens)
        stmts: list[m.Stmt] = parser.parse()
        for error in parser.errors:
            self.reporter.error(error.token.get_location(), error.message)
        self.resolve(stmts)

    def type_of(self, expr: m.Expr) -> Type:
        type: Type = expr.accept(self)
        return type

    def get_type(self, name: str) -> Type:
        """Get a type from its name

        Args:
            name (str): the name of the type

        Raises:
            NameError: if the type is not defined

        Returns:
            Type: the type
        """
        if name in self._local_variables:
            return self._local_variables[name]
        return self.types.get_type(name)

    def get_variable(self, name: str) -> Type:
        if name in self._predicate_params:
            return self._predicate_params[name]
        predicate: Optional[Predicate] = self.types.lookup_predicate(name)
        if predicate is not None:
            return predicate.type

        global_: Optional[Type] = self._preamble.get(name)
        if global_ is not None:
            return global_

        raise NameError(f"Unknown variable '{name}'")

    def resolve(self, stmts: list[m.Stmt]):
        """Process a sequence of statements

        Args:
            stmts (list[m.Stmt]): the statements
        """
        for stmt in stmts:
            stmt.accept(self)

    def assert_bool(self, expr: m.Expr):
        type: Type = self.type_of(expr)
        if not self.types.is_subtype(type, self._bool):
            self.reporter.error(expr.location, f"Must be a boolean but is {type}")

    def visit_type_stmt(self, stmt: m.TypeStmt) -> None:
        name: str = stmt.name.lexeme
        self._current_name = name
        params: list[TypeVar] = self._resolve_type_params(stmt.params)

        type: Type = stmt.type.accept(self)
        if len(params) != 0:
            type = GenericType(name=name, params=params, body=type)
        else:
            type = AliasType(name=name, type=type)
        self.types.define_type(name, type)
        self._local_variables.clear()
        self._current_name = None

    def visit_member_stmt(self, stmt: m.MemberStmt) -> None: ...

    def visit_extend_stmt(self, stmt: m.ExtendStmt) -> None:
        self._resolve_type_params(stmt.params)
        base_name: str = stmt.name.lexeme
        try:
            _ = self.get_type(base_name)
        except NameError:
            self.reporter.error(stmt.name.get_location(), f"Unknown type '{base_name}'")

        for member in stmt.members:
            member_type: Type = member.type.accept(self)
            self.types.define_member(
                base_name,
                member.name.lexeme,
                member_type,
                member.kind == m.MemberKind.METHOD,
            )

    def visit_predicate_stmt(self, stmt: m.PredicateStmt) -> None:
        for spec in stmt.params:
            for param in spec.mixed:
                assert param.name is not None
                self._predicate_params[param.name.lexeme] = param.type.accept(self)

        type: Type = self.type_of(stmt.body)
        params: list[TypedParamSpec] = [
            self._visit_param_spec(spec) for spec in stmt.params
        ]

        if not self._is_valid_predicate(type):
            self.reporter.error(
                stmt.body.location,
                f"Predicate function body must evaluate to a boolean, got {type}",
            )
        if len(params) != 0:
            type = self._bool
            for spec in reversed(params):
                type = Function(
                    pos_args=spec.pos,
                    args=spec.mixed,
                    kw_args=spec.kw,
                    returns=type,
                )
        self._predicate_params = {}
        self.types.define_predicate(
            stmt.name.lexeme,
            Predicate(
                type=type,
                body=stmt.body,
                alias=len(params) == 0,
            ),
        )

    def _is_valid_predicate(self, body: Type) -> bool:
        match body:
            case Function(returns=returns):
                return self._is_valid_predicate(returns)
            case _ if self.types.is_subtype(body, self._bool):
                return True
            case _:
                return False

    def visit_logical_expr(self, expr: m.LogicalExpr) -> Type:
        self.assert_bool(expr.left)
        self.assert_bool(expr.right)
        return self._bool

    def visit_binary_expr(self, expr: m.BinaryExpr) -> Type:
        method: Optional[str] = MIDAS_BINARY_METHODS.get(expr.operator.type)
        if method is None:
            self.logger.warning(f"Unsupported operator {expr.operator.lexeme}")
            self.reporter.warning(
                expr.location, f"Unsupported operator {expr.operator.lexeme}"
            )
            return UnknownType()

        return self._visit_binary_expr(expr.location, expr.left, expr.right, method)

    def _visit_binary_expr(
        self, location: Location, left_expr: m.Expr, right_expr: m.Expr, method: str
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

    def visit_unary_expr(self, expr: m.UnaryExpr) -> Type:
        method: Optional[str] = MIDAS_UNARY_METHODS.get(expr.operator.type)
        if method is None:
            self.logger.warning(f"Unsupported operator {expr.operator.lexeme}")
            self.reporter.warning(
                expr.location, f"Unsupported operator {expr.operator.lexeme}"
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

    def visit_call_expr(self, expr: m.CallExpr) -> Type:
        callee: Type = expr.callee.accept(self)
        positional: list[TypedExpr] = [
            (arg, self.type_of(arg)) for arg in expr.arguments
        ]
        keywords: dict[str, TypedExpr] = {
            name: (arg, self.type_of(arg)) for name, arg in expr.keywords.items()
        }
        return (
            self._get_call_result(
                expr.location,
                callee,
                positional,
                keywords,
            )
            or UnknownType()
        )

    def visit_get_expr(self, expr: m.GetExpr) -> Type:
        object: Type = expr.expr.accept(self)
        member: Optional[Type] = self.types.lookup_member(object, expr.name.lexeme)
        if member is None:
            self.reporter.error(
                expr.location, f"Unknown member '{expr.name.lexeme}' of {object}"
            )
            return UnknownType()
        return member

    def visit_variable_expr(self, expr: m.VariableExpr) -> Type:
        return self.get_variable(expr.name.lexeme)

    def visit_grouping_expr(self, expr: m.GroupingExpr) -> Type:
        return expr.expr.accept(self)

    def visit_literal_expr(self, expr: m.LiteralExpr) -> Type:
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

    def visit_wildcard_expr(self, expr: m.WildcardExpr) -> Type:
        return self.get_variable("_")

    def visit_named_type(self, type: m.NamedType) -> Type:
        name: str = type.name.lexeme
        try:
            return self.get_type(name)
        except NameError:
            msg: str = f"Undefined type {name}"
            if self._current_name == name:
                msg += ". Recursive types are not supported, use an extend block"
            self.reporter.error(type.name.get_location(), msg)
            return UnknownType()

    def visit_generic_type(self, type: m.GenericType) -> Type:
        type_: Type = type.type.accept(self)
        args: list[Type] = [arg.accept(self) for arg in type.args]
        try:
            return self.types.apply_generic(type_, args)
        except Exception as e:
            self.reporter.error(type.location, f"Cannot apply generic type: {e}")
            return UnknownType()

    def visit_constraint_type(self, type: m.ConstraintType) -> Type:
        return ConstraintType(
            type=type.type.accept(self),
            constraint=type.constraint,
        )

    def visit_complex_type(self, type: m.ComplexType) -> ComplexType:
        return ComplexType(
            members={
                member.name.lexeme: member.type.accept(self) for member in type.members
            }
        )

    def visit_extension_type(self, type: m.ExtensionType) -> Type:
        return ExtensionType(
            base=type.base.accept(self),
            extension=self.visit_complex_type(type.extension),
        )

    def visit_function_type(self, type: m.FunctionType) -> Type:
        params: TypedParamSpec = self._visit_param_spec(type.params)
        return Function(
            pos_args=params.pos,
            args=params.mixed,
            kw_args=params.kw,
            returns=type.returns.accept(self),
        )

    def _visit_param_spec(self, spec: m.ParamSpec) -> TypedParamSpec:
        n_pos: int = len(spec.pos)
        n_mixed: int = len(spec.mixed)

        def process_arg(arg: m.FunctionType.Argument, i: int) -> Function.Argument:
            return Function.Argument(
                pos=i,
                name=arg.name.lexeme if arg.name is not None else str(i),
                type=arg.type.accept(self),
                required=arg.required,
            )

        return TypedParamSpec(
            pos=[process_arg(arg, i) for i, arg in enumerate(spec.pos)],
            mixed=[process_arg(arg, i + n_pos) for i, arg in enumerate(spec.mixed)],
            kw=[process_arg(arg, i + n_pos + n_mixed) for i, arg in enumerate(spec.kw)],
        )

    def _resolve_type_params(self, params: list[m.TypeParam]):
        vars: list[TypeVar] = []
        for param in params:
            name: str = param.name.lexeme
            bound: Optional[Type] = None
            if param.bound is not None:
                bound = param.bound.accept(self)
            var = TypeVar(name=name, bound=bound)
            self._local_variables[name] = var
            vars.append(var)
        return vars

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
            if not self.types.is_subtype(arg.type, arg.argument.type):
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
        by_expr: dict[m.Expr, Type] = {}
        for arg in mapped1:
            by_expr[arg.expr] = arg.argument.type

        for arg in mapped2:
            type2: Type = arg.argument.type
            type1: Type = by_expr[arg.expr]
            if not self.types.is_subtype(type1, type2):
                return False
        return True
