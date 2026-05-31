from typing import Optional

import midas.ast.midas as m
from midas.checker.types import BaseType, SimpleType, Type
from midas.resolver.builtin import define_builtins


class MidasResolver(m.Stmt.Visitor[None], m.Expr.Visitor[Type]):
    """A resolver which evaluates Midas type definitions and build a registry"""

    def __init__(self) -> None:
        self._types: dict[str, Type] = {}
        self._operations: dict[tuple[Type, str, Type], Type] = {}

        define_builtins(self)

    def get_type(self, name: str) -> Type:
        """Get a type from its name

        Args:
            name (str): the name of the type

        Raises:
            NameError: if the type is not defined

        Returns:
            Type: the type
        """
        type: Optional[Type] = self._types.get(name)
        if type is None:
            raise NameError(f"Undefined type {name}")
        return type

    def get_operation_result(
        self, left: Type, operator: str, right: Type
    ) -> Optional[Type]:
        """Get the resulting type of an operation

        Args:
            left (Type): the type of the left operand
            operator (str): the operation name
            right (Type): the type of the right operand

        Returns:
            Optional[Type]: the result type, or None if no matching operation was found
        """
        operation: tuple[Type, str, Type] = (left, operator, right)
        result: Optional[Type] = self._operations.get(operation)
        return result

    def define_type(self, name: str, type: Type) -> Type:
        """Define a type in the registry

        Args:
            name (str): the name of the type
            type (Type): the type to define

        Raises:
            ValueError: if a type is already defined with that name

        Returns:
            Type: the defined type
        """
        if name in self._types:
            raise ValueError(f"Type {name} already defined")
        self._types[name] = type
        return type

    def define_operation(self, left: Type, operator: str, right: Type, result: Type):
        """Define an operation in the registry

        Args:
            left (Type): the type of the left operand
            operator (str): the operation name
            right (Type): the type of the right operand
            result (Type): the result type

        Raises:
            ValueError: if an operation is already defined with these operands and name
        """
        operation: tuple[Type, str, Type] = (left, operator, right)
        if operation in self._operations:
            raise ValueError(
                f"Operation {operator} already defined between {left} and {right}"
            )
        self._operations[operation] = result

    def resolve(self, stmts: list[m.Stmt]):
        """Process a sequence of statements

        Args:
            stmts (list[m.Stmt]): the statements
        """
        for stmt in stmts:
            stmt.accept(self)

    def visit_simple_type_stmt(self, stmt: m.SimpleTypeStmt) -> None:
        # TODO generics, optional, constraint
        base: Type = self.get_type(stmt.base.name.lexeme)
        match base:
            case BaseType() | SimpleType():
                type = SimpleType(
                    name=stmt.name.lexeme,
                    base=base,
                )
                self.define_type(type.name, type)
            case _:
                raise TypeError(f"Invalid base {base} for simple type")

    def visit_complex_type_stmt(self, stmt: m.ComplexTypeStmt) -> None: ...

    def visit_property_stmt(self, stmt: m.PropertyStmt) -> None: ...

    def visit_extend_stmt(self, stmt: m.ExtendStmt) -> None:
        base: Type = stmt.type.accept(self)
        for op in stmt.operations:
            right: Type = op.operand.accept(self)
            result: Type = op.result.accept(self)
            self.define_operation(
                left=base,
                operator=op.name.lexeme,
                right=right,
                result=result,
            )

    def visit_op_stmt(self, stmt: m.OpStmt) -> None: ...

    def visit_predicate_stmt(self, stmt: m.PredicateStmt) -> None: ...

    def visit_simple_type_expr(self, expr: m.SimpleTypeExpr) -> Type:
        return self.get_type(expr.name.lexeme)

    def visit_logical_expr(self, expr: m.LogicalExpr) -> Type: ...

    def visit_binary_expr(self, expr: m.BinaryExpr) -> Type: ...

    def visit_unary_expr(self, expr: m.UnaryExpr) -> Type: ...

    def visit_get_expr(self, expr: m.GetExpr) -> Type: ...

    def visit_variable_expr(self, expr: m.VariableExpr) -> Type: ...

    def visit_grouping_expr(self, expr: m.GroupingExpr) -> Type:
        return expr.expr.accept(self)

    def visit_literal_expr(self, expr: m.LiteralExpr) -> Type: ...

    def visit_wildcard_expr(self, expr: m.WildcardExpr) -> Type: ...

    def visit_template_expr(self, expr: m.TemplateExpr) -> Type: ...

    def visit_type_expr(self, expr: m.TypeExpr) -> Type:
        return self.get_type(expr.name.lexeme)
