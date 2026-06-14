from typing import Optional

import midas.ast.midas as m
from midas.checker.types import (
    AliasType,
    ComplexType,
    Operation,
    Type,
    UnknownType,
)
from midas.resolver.builtin import define_builtins


class MidasResolver(m.Stmt.Visitor[None], m.Expr.Visitor[None], m.Type.Visitor[Type]):
    """A resolver which evaluates Midas type definitions and build a registry"""

    def __init__(self) -> None:
        self._types: dict[str, Type] = {}
        self._operations: dict[Operation.CallSignature, Type] = {}

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
        signature: Operation.CallSignature = Operation.CallSignature(
            left=left,
            method=operator,
            right=right,
        )
        result: Optional[Type] = self._operations.get(signature)
        return result

    def get_operations_by_name(self, name: str) -> list[Operation]:
        operations: list[Operation] = []
        for signature, result in self._operations.items():
            if signature.method == name:
                operations.append(
                    Operation(
                        signature=signature,
                        result=result,
                    )
                )
        return operations

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
        signature: Operation.CallSignature = Operation.CallSignature(
            left=left,
            method=operator,
            right=right,
        )
        if signature in self._operations:
            raise ValueError(
                f"Operation {operator} already defined between {left} and {right}"
            )
        self._operations[signature] = result

    def resolve(self, stmts: list[m.Stmt]):
        """Process a sequence of statements

        Args:
            stmts (list[m.Stmt]): the statements
        """
        for stmt in stmts:
            stmt.accept(self)

    def visit_type_stmt(self, stmt: m.TypeStmt) -> None:
        type: Type = stmt.type.accept(self)
        for param in stmt.params:
            if param.bound is not None:
                param.bound.accept(self)
        name: str = stmt.name.lexeme
        self.define_type(name, AliasType(name=name, type=type))

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
        params: list[Type] = [param.accept(self) for param in type.params]
        # TODO
        return UnknownType()

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
