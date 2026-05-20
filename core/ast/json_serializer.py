from core.ast.midas import (
    ConstraintExpr,
    ConstraintStmt,
    Expr,
    LiteralExpr,
    OpStmt,
    PropertyStmt,
    Stmt,
    TypeBodyExpr,
    TypeExpr,
    TypeStmt,
    WildcardExpr,
)


class AstJsonSerializer(Stmt.Visitor[dict], Expr.Visitor[dict]):
    """An AST serializer which produces a JSON-compatible structure"""

    def serialize(self, stmts: list[Stmt]) -> list[dict]:
        return [stmt.accept(self) for stmt in stmts]

    def visit_type_stmt(self, stmt: TypeStmt) -> dict:
        return {
            "_type": "TypeStmt",
            "name": stmt.name.lexeme,
            "bases": [base.accept(self) for base in stmt.bases],
            "body": stmt.body.accept(self) if stmt.body is not None else None,
        }

    def visit_type_expr(self, expr: TypeExpr) -> dict:
        return {
            "_type": "TypeExpr",
            "name": expr.name.lexeme,
            "constraints": [constraint.accept(self) for constraint in expr.constraints],
        }

    def visit_constraint_expr(self, expr: ConstraintExpr) -> dict:
        return {
            "_type": "ConstraintExpr",
            "left": expr.left.accept(self),
            "op": expr.op.lexeme,
            "right": expr.right.accept(self),
        }

    def visit_wildcard_expr(self, expr: WildcardExpr) -> dict:
        return {"_type": "WildcardExpr"}

    def visit_literal_expr(self, expr: LiteralExpr) -> dict:
        return {
            "_type": "LiteralExpr",
            "value": expr.value,
        }

    def visit_type_body_expr(self, expr: TypeBodyExpr) -> dict:
        return {
            "_type": "TypeBodyExpr",
            "properties": [prop.accept(self) for prop in expr.properties],
        }

    def visit_property_stmt(self, stmt: PropertyStmt) -> dict:
        return {
            "_type": "PropertyStmt",
            "name": stmt.name.lexeme,
            "type": stmt.type.accept(self),
        }

    def visit_op_stmt(self, stmt: OpStmt) -> dict:
        return {
            "_type": "OpStmt",
            "left": stmt.left.accept(self),
            "op": stmt.op.lexeme,
            "right": stmt.right.accept(self),
            "result": stmt.result.accept(self),
        }

    def visit_constraint_stmt(self, stmt: ConstraintStmt) -> dict:
        return {
            "_type": "ConstraintStmt",
            "name": stmt.name.lexeme,
            "constraint": stmt.constraint.accept(self),
        }
