import logging
from typing import Optional

import midas.ast.midas as m
from midas.checker.builtins import define_builtins
from midas.checker.registry import TypesRegistry
from midas.checker.reporter import FileReporter, Reporter
from midas.checker.types import (
    AliasType,
    ComplexType,
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

        define_builtins(self.types)

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
        params: list[TypeVar] = self._resolve_type_params(stmt.params)

        name: str = stmt.name.lexeme
        type: Type = stmt.type.accept(self)
        if len(params) != 0:
            type = GenericType(name=name, params=params, body=type)
        else:
            type = AliasType(name=name, type=type)
        self.types.define_type(name, type)
        self._local_variables.clear()

    def visit_property_stmt(self, stmt: m.PropertyStmt) -> None: ...

    def visit_extend_stmt(self, stmt: m.ExtendStmt) -> None:
        self._resolve_type_params(stmt.params)
        base: Type = stmt.type.accept(self)
        for op in stmt.operations:
            right: Type = op.operand.accept(self)
            result: Type = op.result.accept(self)
            self.types.define_operation(
                left=base,
                operator=op.name.lexeme,
                right=right,
                result=result,
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
        return self.get_type(type.name.lexeme)

    def visit_generic_type(self, type: m.GenericType) -> Type:
        type_: Type = type.type.accept(self)
        args: list[Type] = [arg.accept(self) for arg in type.args]
        return self.types.apply_generic(type_, args)

    def visit_constraint_type(self, type: m.ConstraintType) -> Type:
        type_: Type = type.type.accept(self)
        type.constraint.accept(self)
        # TODO
        return UnknownType()

    def visit_complex_type(self, type: m.ComplexType) -> Type:
        return ComplexType(
            properties={
                prop.name.lexeme: prop.type.accept(self) for prop in type.properties
            }
        )
