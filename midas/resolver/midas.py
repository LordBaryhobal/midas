from typing import Optional

import midas.ast.midas as m
from midas.checker.types import BaseType, SimpleType, Type


class MidasResolver(m.Stmt.Visitor[None], m.Expr.Visitor[Type]):
    def __init__(self) -> None:
        self._types: dict[str, Type] = {}
        self._operations: dict[tuple[Type, str, Type], Type] = {}

        self._define_builtin()

    def get_type(self, name: str) -> Type:
        type: Optional[Type] = self._types.get(name)
        if type is None:
            raise NameError(f"Undefined type {name}")
        return type

    def get_operation_result(self, left: Type, operator: str, right: Type) -> Type:
        operation: tuple[Type, str, Type] = (left, operator, right)
        result: Optional[Type] = self._operations.get(operation)
        if result is None:
            raise ValueError(
                f"Undefined operation {operator} between {left} and {right}"
            )
        return result

    def _define_builtin(self):
        self.define_type("bool", BaseType(name="bool"))
        self.define_type("int", BaseType(name="int"))
        self.define_type("float", BaseType(name="float"))
        self.define_type("str", BaseType(name="str"))
        self.define_operation(
            left=self.get_type("int"),
            operator="__add__",
            right=self.get_type("int"),
            result=self.get_type("int"),
        )

    def define_type(self, name: str, type: Type) -> Type:
        if name in self._types:
            raise ValueError(f"Type {name} already defined")
        self._types[name] = type
        return type

    def define_operation(self, left: Type, operator: str, right: Type, result: Type):
        operation: tuple[Type, str, Type] = (left, operator, right)
        if operation in self._operations:
            raise ValueError(
                f"Operation {operator} already defined between {left} and {right}"
            )
        self._operations[operation] = result

    def resolve(self, stmts: list[m.Stmt]):
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
