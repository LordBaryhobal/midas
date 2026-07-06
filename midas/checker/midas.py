import logging
from pathlib import Path
from typing import Optional

import midas.ast.midas as m
from midas.ast.location import Location
from midas.checker.builtins import define_builtins
from midas.checker.dispatcher import CallDispatcher, CallResult
from midas.checker.environment import Environment
from midas.checker.operators import MIDAS_BINARY_METHODS, MIDAS_UNARY_METHODS
from midas.checker.preamble import Preamble
from midas.checker.registry import TypesRegistry
from midas.checker.reporter import FileReporter, Reporter
from midas.checker.types import (
    ColumnType,
    ComplexType,
    ConstraintType,
    DataFrameType,
    DerivedType,
    ExtensionType,
    Function,
    GenericType,
    ParamSpec,
    Predicate,
    Type,
    TypeVar,
    UnknownType,
)
from midas.checker.variance import VarianceInferrer
from midas.lexer.midas import MidasLexer
from midas.lexer.token import Token
from midas.parser.midas import MidasParser


class MidasTyper(m.Stmt.Visitor[None], m.Expr.Visitor[Type], m.Type.Visitor[Type]):
    """A resolver which evaluates Midas type definitions and build a registry"""

    def __init__(self, types: TypesRegistry, reporter: Reporter) -> None:
        self.logger: logging.Logger = logging.getLogger("MidasTyper")
        self.reporter: FileReporter = reporter.for_file(None)
        self.types: TypesRegistry = types
        self.dispatcher: CallDispatcher[m.Expr] = CallDispatcher[m.Expr](
            self.types, self.reporter
        )

        self._local_variables: dict[str, TypeVar] = {}

        self._predicate_params: dict[str, Type] = {}

        self._current_name: Optional[str] = None

        define_builtins(self.types)
        builtins_path: Path = (Path(__file__).parent / "builtins.midas").resolve()
        self.process(builtins_path.read_text(), str(builtins_path))

        self._bool: Type = self.get_type("bool")

        self._preamble: Environment = Preamble(self.types)

    def set_reporter(self, reporter: FileReporter):
        """Set the file reporter to use for diagnostics

        Args:
            reporter (FileReporter): the file reporter
        """
        self.reporter = reporter
        self.dispatcher.set_reporter(reporter)

    def process(self, source: str, path: Optional[str]):
        """Process some Midas source code

        Args:
            source (str): the Midas source code
            path (Optional[str]): the path of the source file, if known
        """
        reporter: FileReporter = self.reporter.for_file(path)
        self.set_reporter(reporter)

        lexer: MidasLexer = MidasLexer(source)
        tokens: list[Token] = lexer.process()
        parser: MidasParser = MidasParser(tokens)
        stmts: list[m.Stmt] = parser.parse()
        for error in parser.errors:
            self.reporter.error(error.token.get_location(), error.message)
        self.resolve(stmts)

    def type_of(self, expr: m.Expr) -> Type:
        """Compute the type of the given expression

        Args:
            expr (m.Expr): the expression to type

        Returns:
            Type: the type of the expression
        """
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
        """Get the type of a variable

        This function will first look into the current predicate's parameters if
        we are in a predicate definition.
        The the variable is looked up in the preamble (i.e. global environment)

        Args:
            name (str): the name of the variable

        Raises:
            NameError: if the variable cannot be found

        Returns:
            Type: the type of the variable
        """
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

        for name, type in self.types._types.items():
            if isinstance(type, GenericType):
                inferrer = VarianceInferrer(self.types)
                self.types._types[name] = inferrer.infer(type)

    def assert_bool(self, expr: m.Expr):
        """Check that the given expression is a subtype of `bool` or report an error

        Args:
            expr (m.Expr): the expression to check
        """
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
            type = DerivedType(name=name, type=type)
        self.types.define_type(name, type)
        self._local_variables.clear()
        self._current_name = None

    def visit_alias_stmt(self, stmt: m.AliasStmt) -> None:
        name: str = stmt.name.lexeme
        self._current_name = name
        type: Type = stmt.type.accept(self)
        self.types.define_type(name, type)
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
                member.kind,
            )

    def visit_predicate_stmt(self, stmt: m.PredicateStmt) -> None:
        for spec in stmt.params:
            for param in spec.mixed:
                assert param.name is not None
                self._predicate_params[param.name.lexeme] = param.type.accept(self)

        type: Type = self.type_of(stmt.body)
        params: list[ParamSpec] = [self._visit_param_spec(spec) for spec in stmt.params]

        if not self._is_valid_predicate(type):
            self.reporter.error(
                stmt.body.location,
                f"Predicate function body must evaluate to a boolean, got {type}",
            )
        if len(params) != 0:
            type = self._bool
            for spec in reversed(params):
                type = Function(
                    params=spec,
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
        """Check whether the given type is valid as a predicate's body

        Accepted types are either subtypes of `bool` or valid predicates

        Args:
            body (Type): the potential predicate body

        Returns:
            bool: `True` if `body` can be a predicate body, `False` otherwise
        """
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
        self,
        location: Location,
        left_expr: m.Expr,
        right_expr: m.Expr,
        method: str,
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

        result: CallResult = self.dispatcher.get_result(
            location=location,
            callee=operation,
            positional=[(right_expr, right)],
            keywords={},
        )
        return result.result

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

        result: CallResult = self.dispatcher.get_result(
            location=expr.location,
            callee=operation,
            positional=[],
            keywords={},
        )
        return result.result

    def visit_call_expr(self, expr: m.CallExpr) -> Type:
        callee: Type = expr.callee.accept(self)
        positional: list[tuple[m.Expr, Type]] = [
            (arg, self.type_of(arg)) for arg in expr.arguments
        ]
        keywords: dict[str, tuple[m.Expr, Type]] = {
            name: (arg, self.type_of(arg)) for name, arg in expr.keywords.items()
        }
        result: CallResult = self.dispatcher.get_result(
            location=expr.location,
            callee=callee,
            positional=positional,
            keywords=keywords,
        )
        return result.result

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
        match type.type:
            case m.NamedType(name=Token(lexeme="Column")):
                if len(type.args) != 1:
                    self.reporter.error(
                        type.location,
                        f"Column requires 1 type argument, {len(type.args)} provided",
                    )
                    return ColumnType(type=UnknownType())
                return ColumnType(type=type.args[0].accept(self))

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
        return Function(
            params=self._visit_param_spec(type.params),
            returns=type.returns.accept(self),
        )

    def _visit_param_spec(self, spec: m.ParamSpec) -> ParamSpec:
        n_pos: int = len(spec.pos)
        n_mixed: int = len(spec.mixed)

        def process_param(
            param: m.FunctionType.Parameter, i: int
        ) -> Function.Parameter:
            return Function.Parameter(
                pos=i,
                name=param.name.lexeme if param.name is not None else str(i),
                type=param.type.accept(self),
                required=param.required,
            )

        return ParamSpec(
            pos=[process_param(param, i) for i, param in enumerate(spec.pos)],
            mixed=[
                process_param(param, i + n_pos) for i, param in enumerate(spec.mixed)
            ],
            kw=[
                process_param(param, i + n_pos + n_mixed)
                for i, param in enumerate(spec.kw)
            ],
        )

    def visit_frame_type(self, type: m.FrameType) -> Type:
        def process_column(i: int, col: m.FrameType.Column) -> DataFrameType.Column:
            return DataFrameType.Column(
                index=i,
                name=col.name.lexeme,
                type=ColumnType(type=col.type.accept(self)),
            )

        return DataFrameType(
            columns=[process_column(i, col) for i, col in enumerate(type.columns)]
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
