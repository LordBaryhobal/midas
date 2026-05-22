from typing import Optional, Sequence

from core.ast.midas import (
    BinaryExpr,
    ComplexTypeStmt,
    Expr,
    ExtendStmt,
    GetExpr,
    GroupingExpr,
    LiteralExpr,
    LogicalExpr,
    OpStmt,
    PredicateStmt,
    PropertyStmt,
    SimpleTypeExpr,
    SimpleTypeStmt,
    Stmt,
    TemplateExpr,
    TypeExpr,
    UnaryExpr,
    VariableExpr,
    WildcardExpr,
)


class AstJsonSerializer(Stmt.Visitor[dict], Expr.Visitor[dict]):
    """An AST serializer which produces a JSON-compatible structure"""

    def serialize(self, stmts: list[Stmt]) -> list[dict]:
        return [stmt.accept(self) for stmt in stmts]

    def _serialize_optional(self, element: Optional[Stmt | Expr]) -> Optional[dict]:
        if element is None:
            return None
        return element.accept(self)

    def _serialize_list(self, elements: Sequence[Stmt | Expr]) -> list[dict]:
        return [element.accept(self) for element in elements]

    def visit_simple_type_stmt(self, stmt: SimpleTypeStmt) -> dict:
        return {
            "_type": "SimpleTypeStmt",
            "template": self._serialize_optional(stmt.template),
            "name": stmt.name.lexeme,
            "base": stmt.base.accept(self),
            "constraint": self._serialize_optional(stmt.constraint),
        }

    def visit_complex_type_stmt(self, stmt: ComplexTypeStmt) -> dict:
        return {
            "_type": "ComplexTypeStmt",
            "name": stmt.name.lexeme,
            "template": self._serialize_optional(stmt.template),
            "properties": self._serialize_list(stmt.properties),
        }

    def visit_property_stmt(self, stmt: PropertyStmt) -> dict:
        return {
            "_type": "PropertyStmt",
            "name": stmt.name.lexeme,
            "type": stmt.type.accept(self),
            "constraint": self._serialize_optional(stmt.constraint),
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

    def visit_simple_type_expr(self, expr: SimpleTypeExpr) -> dict:
        return {
            "_type": "SimpleTypeExpr",
            "name": expr.name.lexeme,
            "optional": expr.optional,
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

    def visit_template_expr(self, expr: TemplateExpr) -> dict:
        return {
            "_type": "TemplateExpr",
            "type": expr.type.accept(self),
        }

    def visit_type_expr(self, expr: TypeExpr) -> dict:
        return {
            "_type": "TypeExpr",
            "name": expr.name.lexeme,
            "template": self._serialize_optional(expr.template),
            "optional": expr.optional,
        }
