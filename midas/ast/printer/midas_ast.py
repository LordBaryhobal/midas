import midas.ast.midas as m
from midas.ast.printer.base import AstPrinter


class MidasAstPrinter(
    AstPrinter,
    m.Expr.Visitor[None],
    m.Stmt.Visitor[None],
    m.Type.Visitor[None],
):
    # Statements

    def visit_type_stmt(self, stmt: m.TypeStmt) -> None:
        self._write_line("TypeStmt")
        with self._child_level():
            self._write_line(f'name: "{stmt.name.lexeme}"')
            self._write_sequence(
                "params",
                stmt.params,
                print_func=self._print_type_param,
            )
            self._write_line("type", last=True)
            with self._child_level(single=True):
                stmt.type.accept(self)

    def visit_alias_stmt(self, stmt: m.AliasStmt) -> None:
        self._write_line("AliasStmt")
        with self._child_level():
            self._write_line(f'name: "{stmt.name.lexeme}"')
            self._write_line("type", last=True)
            with self._child_level(single=True):
                stmt.type.accept(self)

    def _print_type_param(self, param: m.TypeParam) -> None:
        self._write_line("Param")
        with self._child_level():
            self._write_line(f'name: "{param.name.lexeme}"')
            self._write_optional_child("bound", param.bound, last=True)

    def visit_member_stmt(self, stmt: m.MemberStmt):
        self._write_line("MemberStmt")
        with self._child_level():
            self._write_line(f"kind: {stmt.kind.name}")
            self._write_line(f'name: "{stmt.name.lexeme}"')
            self._write_line("type", last=True)
            with self._child_level(single=True):
                stmt.type.accept(self)

    def visit_extend_stmt(self, stmt: m.ExtendStmt) -> None:
        self._write_line("ExtendStmt")
        with self._child_level():
            self._write_line(f'name: "{stmt.name.lexeme}"')
            self._write_sequence(
                "params",
                stmt.params,
                print_func=self._print_type_param,
            )
            self._write_sequence("members", stmt.members, last=True)

    def visit_predicate_stmt(self, stmt: m.PredicateStmt):
        self._write_line("PredicateStmt")
        with self._child_level():
            self._write_line(f'name: "{stmt.name.lexeme}"')
            self._write_sequence(
                "params",
                stmt.params,
                print_func=self._visit_param_spec,
            )
            self._write_line("body", last=True)
            with self._child_level(single=True):
                stmt.body.accept(self)

    # Expressions

    def visit_logical_expr(self, expr: m.LogicalExpr):
        self._write_line("LogicalExpr")
        with self._child_level():
            self._write_line("left")
            with self._child_level(single=True):
                expr.left.accept(self)

            self._write_line(f"operator: {expr.operator.lexeme}")

            self._write_line("right", last=True)
            with self._child_level(single=True):
                expr.right.accept(self)

    def visit_binary_expr(self, expr: m.BinaryExpr):
        self._write_line("BinaryExpr")
        with self._child_level():
            self._write_line("left")
            with self._child_level(single=True):
                expr.left.accept(self)

            self._write_line(f"operator: {expr.operator.lexeme}")

            self._write_line("right", last=True)
            with self._child_level(single=True):
                expr.right.accept(self)

    def visit_unary_expr(self, expr: m.UnaryExpr):
        self._write_line("UnaryExpr")
        with self._child_level():
            self._write_line(f"operator: {expr.operator.lexeme}")

            self._write_line("right", last=True)
            with self._child_level(single=True):
                expr.right.accept(self)

    def visit_call_expr(self, expr: m.CallExpr) -> None:
        self._write_line("CallExpr")
        with self._child_level():
            self._write_line("callee")
            with self._child_level(single=True):
                expr.callee.accept(self)
            self._write_sequence("arguments", expr.arguments)
            self._write_line("keywords", last=True)
            with self._child_level():
                for i, (name, arg) in enumerate(expr.keywords.items()):
                    self._idx = i
                    if i == len(expr.keywords) - 1:
                        self._mark_last()
                    self._write_line(name)
                    with self._child_level(single=True):
                        arg.accept(self)

    def visit_get_expr(self, expr: m.GetExpr):
        self._write_line("GetExpr")
        with self._child_level():
            self._write_line("expr")
            with self._child_level(single=True):
                expr.expr.accept(self)
            self._write_line(f'name: "{expr.name.lexeme}"', last=True)

    def visit_variable_expr(self, expr: m.VariableExpr):
        self._write_line("VariableExpr")
        with self._child_level():
            self._write_line(f'name: "{expr.name.lexeme}"', last=True)

    def visit_grouping_expr(self, expr: m.GroupingExpr):
        self._write_line("GroupingExpr")
        with self._child_level():
            self._write_line("expr", last=True)
            with self._child_level(single=True):
                expr.expr.accept(self)

    def visit_literal_expr(self, expr: m.LiteralExpr) -> None:
        self._write_line("LiteralExpr")
        with self._child_level():
            self._write_line(f"value: {expr.value}", last=True)

    def visit_wildcard_expr(self, expr: m.WildcardExpr) -> None:
        self._write_line("WildcardExpr")

    # Types

    def visit_named_type(self, type: m.NamedType) -> None:
        self._write_line("NamedType")
        with self._child_level():
            self._write_line(f'name: "{type.name.lexeme}"', last=True)

    def visit_generic_type(self, type: m.GenericType) -> None:
        self._write_line("GenericType")
        with self._child_level():
            self._write_line("type")
            with self._child_level():
                type.type.accept(self)
            self._write_sequence("args", type.args, last=True)

    def visit_constraint_type(self, type: m.ConstraintType) -> None:
        self._write_line("ConstraintType")
        with self._child_level():
            self._write_line("type")
            with self._child_level(single=True):
                type.type.accept(self)
            self._write_line("constraint", last=True)
            with self._child_level(single=True):
                type.constraint.accept(self)

    def visit_function_type(self, type: m.FunctionType) -> None:
        self._write_line("FunctionType")
        with self._child_level():
            self._write_line("params")
            with self._child_level(single=True):
                self._visit_param_spec(type.params)

            self._write_line("returns", last=True)
            with self._child_level(single=True):
                type.returns.accept(self)

    def _visit_param_spec(self, spec: m.ParamSpec) -> None:
        self._write_line("ParamSpec")
        with self._child_level():
            self._write_sequence(
                "pos",
                spec.pos,
                print_func=self._print_param,
            )
            self._write_sequence(
                "mixed",
                spec.mixed,
                print_func=self._print_param,
            )
            self._write_sequence(
                "kw",
                spec.kw,
                print_func=self._print_param,
                last=True,
            )

    def _print_param(self, param: m.FunctionType.Parameter) -> None:
        self._write_line("Parameter")
        with self._child_level():
            name: str = "None"
            if param.name is not None:
                name = f'"{param.name.lexeme}"'
            self._write_line(f"name: {name}")
            self._write_line("type")
            with self._child_level(single=True):
                param.type.accept(self)
            self._write_line(f"required: {param.required}", last=True)

    def visit_frame_type(self, type: m.FrameType) -> None:
        self._write_line("FrameType")
        with self._child_level(single=True):
            self._write_sequence(
                "columns",
                type.columns,
                print_func=self._print_frame_column,
            )

    def _print_frame_column(self, column: m.FrameType.Column) -> None:
        self._write_line("Column")
        with self._child_level():
            self._write_line(f'name: "{column.name.lexeme}"')
            self._write_line("type")
            with self._child_level(single=True):
                column.type.accept(self)
