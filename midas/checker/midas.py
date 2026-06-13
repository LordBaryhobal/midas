import logging
from pathlib import Path
from typing import Optional

import midas.ast.midas as m
from midas.checker.builtins import define_builtins
from midas.checker.registry import TypesRegistry
from midas.checker.reporter import FileReporter, Reporter
from midas.checker.types import (
    AliasType,
    ComplexType,
    ExtensionType,
    Function,
    GenericType,
    Type,
    TypeVar,
    UnknownType,
)
from midas.lexer.midas import MidasLexer
from midas.lexer.token import Token
from midas.parser.midas import MidasParser


class MidasTyper(m.Stmt.Visitor[None], m.Expr.Visitor[None], m.Type.Visitor[Type]):
    """A resolver which evaluates Midas type definitions and build a registry"""

    def __init__(self, types: TypesRegistry, reporter: Reporter) -> None:
        self.logger: logging.Logger = logging.getLogger("MidasTyper")
        self.reporter: FileReporter = reporter.for_file(None)

        self.types: TypesRegistry = types
        self._local_variables: dict[str, TypeVar] = {}

        self._current_name: Optional[str] = None

        define_builtins(self.types)
        builtins_path: Path = (Path(__file__).parent / "builtins.midas").resolve()
        self.process(builtins_path.read_text(), str(builtins_path))

    def process(self, source: str, path: Optional[str]):
        self.reporter = self.reporter.for_file(path)
        lexer: MidasLexer = MidasLexer(source)
        tokens: list[Token] = lexer.process()
        parser: MidasParser = MidasParser(tokens)
        stmts: list[m.Stmt] = parser.parse()
        self.resolve(stmts)

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

    def resolve(self, stmts: list[m.Stmt]):
        """Process a sequence of statements

        Args:
            stmts (list[m.Stmt]): the statements
        """
        for stmt in stmts:
            stmt.accept(self)

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

    def visit_op_stmt(self, stmt: m.OpStmt) -> None: ...

    def visit_predicate_stmt(self, stmt: m.PredicateStmt) -> None: ...

    def visit_logical_expr(self, expr: m.LogicalExpr) -> None: ...

    def visit_binary_expr(self, expr: m.BinaryExpr) -> None: ...

    def visit_unary_expr(self, expr: m.UnaryExpr) -> None: ...

    def visit_get_expr(self, expr: m.GetExpr) -> None: ...

    def visit_variable_expr(self, expr: m.VariableExpr) -> None: ...

    def visit_grouping_expr(self, expr: m.GroupingExpr) -> None:
        return expr.expr.accept(self)

    def visit_literal_expr(self, expr: m.LiteralExpr) -> None: ...

    def visit_wildcard_expr(self, expr: m.WildcardExpr) -> None: ...

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
        type_: Type = type.type.accept(self)
        type.constraint.accept(self)
        # TODO
        return UnknownType()

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
            pos_args=[
                Function.Argument(
                    pos=i,
                    name=arg.name.lexeme if arg.name is not None else str(i),
                    type=arg.type.accept(self),
                    required=arg.required,
                )
                for i, arg in enumerate(type.pos_args)
            ],
            args=[],
            kw_args=[
                Function.Argument(
                    pos=i,
                    name=arg.name.lexeme if arg.name is not None else str(i),
                    type=arg.type.accept(self),
                    required=arg.required,
                )
                for i, arg in enumerate(type.kw_args, start=len(type.pos_args))
            ],
            returns=type.returns.accept(self),
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
