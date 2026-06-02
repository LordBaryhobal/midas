from typing import Optional, Sequence

from midas.ast.midas import (
    BinaryExpr,
    ComplexType,
    ConstraintType,
    Expr,
    ExtendStmt,
    GenericType,
    GetExpr,
    GroupingExpr,
    LiteralExpr,
    LogicalExpr,
    NamedType,
    OpStmt,
    PredicateStmt,
    PropertyStmt,
    Stmt,
    Type,
    TypeStmt,
    UnaryExpr,
    VariableExpr,
    WildcardExpr,
)


class MidasAstJsonSerializer(
    Stmt.Visitor[dict], Expr.Visitor[dict], Type.Visitor[dict]
):
    """An AST serializer which produces a JSON-compatible structure"""

    def serialize(self, stmts: list[Stmt]) -> list[dict]:
        return [stmt.accept(self) for stmt in stmts]

    def _serialize_optional(
        self, element: Optional[Stmt | Expr | Type]
    ) -> Optional[dict]:
        if element is None:
            return None
        return element.accept(self)

    def _serialize_list(self, elements: Sequence[Stmt | Expr | Type]) -> list[dict]:
        return [element.accept(self) for element in elements]

    def visit_type_stmt(self, stmt: TypeStmt) -> dict:
        return {
            "_type": "TypeStmt",
            "name": stmt.name.lexeme,
            "params": [
                self._serialize_type_stmt_template_param(param) for param in stmt.params
            ],
            "type": stmt.type.accept(self),
        }

    def _serialize_type_stmt_template_param(self, param: TypeStmt.Param) -> dict:
        return {
            "name": param.name.lexeme,
            "bound": self._serialize_optional(param.bound),
        }

    def visit_property_stmt(self, stmt: PropertyStmt) -> dict:
        return {
            "_type": "PropertyStmt",
            "name": stmt.name.lexeme,
            "type": stmt.type.accept(self),
        }

    def visit_extend_stmt(self, stmt: ExtendStmt) -> dict:
        return {
            "_type": "ExtendStmt",
            "type": stmt.type.accept(self),
            "operations": self._serialize_list(stmt.operations),
        }

    def visit_op_stmt(self, stmt: OpStmt) -> dict:
        return {
            "_type": "OpStmt",
            "name": stmt.name.lexeme,
            "operand": stmt.operand.accept(self),
            "result": stmt.result.accept(self),
        }

    def visit_predicate_stmt(self, stmt: PredicateStmt) -> dict:
        return {
            "_type": "PredicateStmt",
            "name": stmt.name.lexeme,
            "subject": stmt.subject.lexeme,
            "type": stmt.type.accept(self),
            "condition": stmt.condition.accept(self),
        }

    def visit_logical_expr(self, expr: LogicalExpr) -> dict:
        return {
            "_type": "LogicalExpr",
            "left": expr.left.accept(self),
            "operator": expr.operator.lexeme,
            "right": expr.right.accept(self),
        }

    def visit_binary_expr(self, expr: BinaryExpr) -> dict:
        return {
            "_type": "BinaryExpr",
            "left": expr.left.accept(self),
            "operator": expr.operator.lexeme,
            "right": expr.right.accept(self),
        }

    def visit_unary_expr(self, expr: UnaryExpr) -> dict:
        return {
            "_type": "UnaryExpr",
            "operator": expr.operator.lexeme,
            "right": expr.right.accept(self),
        }

    def visit_get_expr(self, expr: GetExpr) -> dict:
        return {
            "_type": "GetExpr",
            "expr": expr.expr.accept(self),
            "name": expr.name.lexeme,
        }

    def visit_variable_expr(self, expr: VariableExpr) -> dict:
        return {
            "_type": "VariableExpr",
            "name": expr.name.lexeme,
        }

    def visit_grouping_expr(self, expr: GroupingExpr) -> dict:
        return {
            "_type": "GroupingExpr",
            "expr": expr.expr.accept(self),
        }

    def visit_literal_expr(self, expr: LiteralExpr) -> dict:
        return {
            "_type": "LiteralExpr",
            "value": expr.value,
        }

    def visit_wildcard_expr(self, expr: WildcardExpr) -> dict:
        return {"_type": "WildcardExpr"}

    def visit_named_type(self, type: NamedType) -> dict:
        return {
            "_type": "NamedType",
            "name": type.name.lexeme,
        }

    def visit_generic_type(self, type: GenericType) -> dict:
        return {
            "_type": "GenericType",
            "type": type.type.accept(self),
            "params": self._serialize_list(type.params),
        }

    def visit_constraint_type(self, type: ConstraintType) -> dict:
        return {
            "_type": "ConstraintType",
            "type": type.type.accept(self),
            "constraint": type.constraint.accept(self),
        }

    def visit_complex_type(self, type: ComplexType) -> dict:
        return {
            "_type": "ComplexType",
            "properties": self._serialize_list(type.properties),
        }
