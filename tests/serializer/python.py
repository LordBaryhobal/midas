import ast
from typing import Optional, Sequence, Type

from midas.ast.python import (
    AssignStmt,
    BaseType,
    BinaryExpr,
    CallExpr,
    CastExpr,
    CompareExpr,
    ConstraintType,
    Expr,
    ExpressionStmt,
    FrameColumn,
    FrameType,
    Function,
    GetExpr,
    IfStmt,
    ListExpr,
    LiteralExpr,
    LogicalExpr,
    MidasType,
    Pass,
    ReturnStmt,
    SliceExpr,
    Stmt,
    SubscriptExpr,
    TernaryExpr,
    TypeAssign,
    UnaryExpr,
    VariableExpr,
)

unary_ops: dict[Type[ast.unaryop], str] = {
    ast.Invert: "~",
    ast.Not: "not",
    ast.UAdd: "+",
    ast.USub: "-",
}
binary_ops: dict[Type[ast.operator], str] = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.MatMult: "@",
    ast.Div: "/",
    ast.Mod: "%",
    ast.LShift: "<<",
    ast.RShift: ">>",
    ast.BitOr: "|",
    ast.BitXor: "^",
    ast.BitAnd: "&",
    ast.FloorDiv: "//",
    ast.Pow: "**",
}
compare_ops: dict[Type[ast.cmpop], str] = {
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.Is: "is",
    ast.IsNot: "is not",
    ast.In: "in",
    ast.NotIn: "not in",
}
boolean_ops: dict[Type[ast.boolop], str] = {
    ast.And: "and",
    ast.Or: "or",
}


class PythonAstJsonSerializer(
    Stmt.Visitor[dict], Expr.Visitor[dict], MidasType.Visitor[dict]
):
    """An AST serializer which produces a JSON-compatible structure"""

    def serialize(self, stmts: list[Stmt]) -> list[dict]:
        return [stmt.accept(self) for stmt in stmts]

    def _serialize_optional(
        self, element: Optional[Stmt | Expr | MidasType]
    ) -> Optional[dict]:
        if element is None:
            return None
        return element.accept(self)

    def _serialize_list(
        self, elements: Sequence[Stmt | Expr | MidasType]
    ) -> list[dict]:
        return [element.accept(self) for element in elements]

    def visit_base_type(self, node: BaseType) -> dict:
        return {
            "_type": "BaseType",
            "base": node.base,
            "param": self._serialize_optional(node.param),
        }

    def visit_constraint_type(self, node: ConstraintType) -> dict:
        return {
            "_type": "ConstraintType",
            "type": node.type.accept(self),
            "constraint": ast.unparse(node.constraint),
        }

    def visit_frame_column(self, node: FrameColumn) -> dict:
        return {
            "_type": "FrameColumn",
            "name": node.name,
            "type": self._serialize_optional(node.type),
        }

    def visit_frame_type(self, node: FrameType) -> dict:
        return {
            "_type": "FrameType",
            "columns": self._serialize_list(node.columns),
        }

    def visit_expression_stmt(self, stmt: ExpressionStmt) -> dict:
        return {
            "_type": "ExpressionStmt",
            "expr": stmt.expr.accept(self),
        }

    def _serialize_argument(self, arg: Function.Argument) -> dict:
        return {
            "name": arg.name,
            "type": self._serialize_optional(arg.type),
            "default": self._serialize_optional(arg.default),
        }

    def visit_function(self, stmt: Function) -> dict:
        return {
            "_type": "Function",
            "name": stmt.name,
            "posonlyargs": [self._serialize_argument(arg) for arg in stmt.posonlyargs],
            "args": [self._serialize_argument(arg) for arg in stmt.args],
            "sink": (
                self._serialize_argument(stmt.sink) if stmt.sink is not None else None
            ),
            "kwonlyargs": [self._serialize_argument(arg) for arg in stmt.kwonlyargs],
            "kw_sink": (
                self._serialize_argument(stmt.kw_sink)
                if stmt.kw_sink is not None
                else None
            ),
            "returns": self._serialize_optional(stmt.returns),
            "body": self._serialize_list(stmt.body),
        }

    def visit_type_assign(self, stmt: TypeAssign) -> dict:
        return {
            "_type": "TypeAssign",
            "name": stmt.name,
            "type": stmt.type.accept(self),
        }

    def visit_assign_stmt(self, stmt: AssignStmt) -> dict:
        return {
            "_type": "AssignStmt",
            "targets": self._serialize_list(stmt.targets),
            "value": stmt.value.accept(self),
        }

    def visit_return_stmt(self, stmt: ReturnStmt) -> dict:
        return {
            "_type": "ReturnStmt",
            "value": self._serialize_optional(stmt.value),
        }

    def visit_if_stmt(self, stmt: IfStmt) -> dict:
        return {
            "_type": "IfStmt",
            "test": stmt.test.accept(self),
            "body": self._serialize_list(stmt.body),
            "orelse": self._serialize_list(stmt.orelse),
        }

    def visit_pass(self, stmt: Pass) -> dict:
        return {
            "_type": "Pass",
        }

    def visit_binary_expr(self, expr: BinaryExpr) -> dict:
        return {
            "_type": "BinaryExpr",
            "left": expr.left.accept(self),
            "operator": binary_ops[expr.operator.__class__],
            "right": expr.right.accept(self),
        }

    def visit_compare_expr(self, expr: CompareExpr) -> dict:
        return {
            "_type": "CompareExpr",
            "left": expr.left.accept(self),
            "operator": compare_ops[expr.operator.__class__],
            "right": expr.right.accept(self),
        }

    def visit_unary_expr(self, expr: UnaryExpr) -> dict:
        return {
            "_type": "UnaryExpr",
            "operator": unary_ops[expr.operator.__class__],
            "right": expr.right.accept(self),
        }

    def visit_call_expr(self, expr: CallExpr) -> dict:
        return {
            "_type": "CallExpr",
            "callee": expr.callee.accept(self),
            "arguments": self._serialize_list(expr.arguments),
            "keywords": {name: arg.accept(self) for name, arg in expr.keywords.items()},
        }

    def visit_get_expr(self, expr: GetExpr) -> dict:
        return {
            "_type": "GetExpr",
            "object": expr.object.accept(self),
            "name": expr.name,
        }

    def visit_literal_expr(self, expr: LiteralExpr) -> dict:
        return {
            "_type": "LiteralExpr",
            "value": expr.value,
        }

    def visit_variable_expr(self, expr: VariableExpr) -> dict:
        return {
            "_type": "VariableExpr",
            "name": expr.name,
        }

    def visit_logical_expr(self, expr: LogicalExpr) -> dict:
        return {
            "_type": "LogicalExpr",
            "left": expr.left.accept(self),
            "operator": boolean_ops[expr.operator.__class__],
            "right": expr.right.accept(self),
        }

    def visit_cast_expr(self, expr: CastExpr) -> dict:
        return {
            "_type": "CastExpr",
            "type": expr.type.accept(self),
            "expr": expr.expr.accept(self),
        }

    def visit_ternary_expr(self, expr: TernaryExpr) -> dict:
        return {
            "_type": "TernaryExpr",
            "test": expr.test.accept(self),
            "if_true": expr.if_true.accept(self),
            "if_false": expr.if_false.accept(self),
        }

    def visit_list_expr(self, expr: ListExpr) -> dict:
        return {
            "_type": "ListExpr",
            "items": [item.accept(self) for item in expr.items],
        }

    def visit_subscript_expr(self, expr: SubscriptExpr) -> dict:
        return {
            "_type": "SubscriptExpr",
            "object": expr.object.accept(self),
            "index": expr.index.accept(self),
        }

    def visit_slice_expr(self, expr: SliceExpr) -> dict:
        return {
            "_type": "SliceExpr",
            "lower": self._serialize_optional(expr.lower),
            "upper": self._serialize_optional(expr.upper),
            "step": self._serialize_optional(expr.step),
        }
