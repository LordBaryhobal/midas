from typing import Optional, Sequence

from midas.ast.midas import (
    AliasStmt,
    BinaryExpr,
    CallExpr,
    ComplexType,
    ConstraintType,
    Expr,
    ExtendStmt,
    ExtensionType,
    FrameType,
    FunctionType,
    GenericType,
    GetExpr,
    GroupingExpr,
    LiteralExpr,
    LogicalExpr,
    MemberStmt,
    NamedType,
    ParamSpec,
    PredicateStmt,
    Stmt,
    Type,
    TypeParam,
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
            "params": [self._serialize_type_param(param) for param in stmt.params],
            "type": stmt.type.accept(self),
        }

    def _serialize_type_param(self, param: TypeParam) -> dict:
        return {
            "name": param.name.lexeme,
            "bound": self._serialize_optional(param.bound),
        }

    def visit_alias_stmt(self, stmt: AliasStmt) -> dict:
        return {
            "_type": "AliasStmt",
            "name": stmt.name.lexeme,
            "type": stmt.type.accept(self),
        }

    def visit_member_stmt(self, stmt: MemberStmt) -> dict:
        return {
            "_type": "MemberStmt",
            "kind": stmt.kind.name,
            "name": stmt.name.lexeme,
            "type": stmt.type.accept(self),
        }

    def visit_extend_stmt(self, stmt: ExtendStmt) -> dict:
        return {
            "_type": "ExtendStmt",
            "name": stmt.name.lexeme,
            "params": [self._serialize_type_param(param) for param in stmt.params],
            "members": self._serialize_list(stmt.members),
        }

    def visit_predicate_stmt(self, stmt: PredicateStmt) -> dict:
        return {
            "_type": "PredicateStmt",
            "name": stmt.name.lexeme,
            "params": [self._serialize_param_spec(spec) for spec in stmt.params],
            "body": stmt.body.accept(self),
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
            "args": self._serialize_list(type.args),
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
            "members": self._serialize_list(type.members),
        }

    def visit_function_type(self, type: FunctionType) -> dict:
        return {
            "_type": "FunctionType",
            "params": self._serialize_param_spec(type.params),
            "returns": type.returns.accept(self),
        }

    def _serialize_param_spec(self, spec: ParamSpec) -> dict:
        return {
            "_type": "ParamSpec",
            "pos": [self._serialize_func_arg(arg) for arg in spec.pos],
            "mixed": [self._serialize_func_arg(arg) for arg in spec.mixed],
            "kw": [self._serialize_func_arg(arg) for arg in spec.kw],
        }

    def _serialize_func_arg(self, arg: FunctionType.Argument) -> dict:
        return {
            "name": arg.name.lexeme if arg.name is not None else None,
            "type": arg.type.accept(self),
            "required": arg.required,
        }

    def visit_extension_type(self, type: ExtensionType) -> dict:
        return {
            "_type": "ExtensionType",
            "base": type.base.accept(self),
            "extension": type.extension.accept(self),
        }

    def visit_frame_type(self, type: FrameType) -> dict:
        return {
            "_type": "FrameType",
            "columns": [self._serialize_column(col) for col in type.columns],
        }

    def _serialize_column(self, column: FrameType.Column):
        return {
            "name": column.name.lexeme,
            "type": column.type.accept(self),
        }
