import ast
from typing import final

import midas.ast.python as p
from midas.ast.printer.base import AstPrinter


@final
class PythonAstPrinter(
    AstPrinter,
    p.MidasType.Visitor[None],
    p.Stmt.Visitor[None],
    p.Expr.Visitor[None],
):
    # Types

    def visit_base_type(self, node: p.BaseType) -> None:
        self._write_line("BaseType")
        with self._child_level():
            self._write_line(f"base: {node.base}")
            self._write_sequence("args", node.args, last=True)

    def visit_frame_column(self, node: p.FrameColumn) -> None:
        self._write_line("FrameColumn")
        with self._child_level():
            self._write_line(f"name: {node.name}")
            self._write_optional_child("type", node.type, last=True)

    def visit_frame_type(self, node: p.FrameType) -> None:
        self._write_line("FrameType")
        with self._child_level(single=True):
            self._write_sequence("columns", node.columns)

    # Statements

    def visit_expression_stmt(self, stmt: p.ExpressionStmt) -> None:
        stmt.expr.accept(self)

    def visit_function(self, stmt: p.Function) -> None:
        self._write_line("Function")
        with self._child_level():
            self._write_line(f"name: {stmt.name}")
            self._write_line("params")
            with self._child_level():
                self._print_param_spec(stmt.params)

            self._write_optional_child("returns", stmt.returns)
            self._write_sequence("body", stmt.body, last=True)

    def _print_param_spec(self, spec: p.ParamSpec) -> None:
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

    def _print_param(self, param: p.Function.Parameter) -> None:
        self._write_line("Parameter")
        with self._child_level():
            self._write_line(f"name: {param.name}")
            self._write_optional_child("type", param.type, last=True)

    def visit_type_assign(self, stmt: p.TypeAssign) -> None:
        self._write_line("TypeAssign")
        with self._child_level():
            self._write_line(f"name: {stmt.name}")
            self._write_line("type", last=True)
            with self._child_level(single=True):
                stmt.type.accept(self)

    def visit_assign_stmt(self, stmt: p.AssignStmt) -> None:
        self._write_line("AssignStmt")
        with self._child_level():
            self._write_sequence("targets", stmt.targets)
            self._write_line("value", last=True)
            with self._child_level(single=True):
                stmt.value.accept(self)

    def visit_return_stmt(self, stmt: p.ReturnStmt) -> None:
        self._write_line("ReturnStmt")
        with self._child_level():
            self._write_optional_child("value", stmt.value, last=True)

    def visit_if_stmt(self, stmt: p.IfStmt) -> None:
        self._write_line("IfStmt")
        with self._child_level():
            self._write_line("test")
            with self._child_level(single=True):
                stmt.test.accept(self)
            self._write_sequence("body", stmt.body)
            self._write_sequence("orelse", stmt.orelse, last=True)

    def visit_pass(self, stmt: p.Pass) -> None:
        self._write_line("Pass")

    def visit_for_stmt(self, stmt: p.ForStmt) -> None:
        self._write_line("ForStmt")
        with self._child_level():
            self._write_line("target")
            with self._child_level(single=True):
                stmt.target.accept(self)
            self._write_line("iterator")
            with self._child_level(single=True):
                stmt.iterator.accept(self)
            self._write_sequence("body", stmt.body, last=True)

    def visit_raw_stmt(self, stmt: p.RawStmt) -> None:
        self._write_line("RawStmt")
        with self._child_level(single=True):
            self._write_line(f"stmt: {ast.unparse(stmt.stmt)}")

    # Expressions

    def visit_binary_expr(self, expr: p.BinaryExpr) -> None:
        self._write_line("BinaryExpr")
        with self._child_level():
            self._write_line("left")
            with self._child_level(single=True):
                expr.left.accept(self)

            self._write_line(f"operator: {expr.operator.__class__.__name__}")

            self._write_line("right", last=True)
            with self._child_level(single=True):
                expr.right.accept(self)

    def visit_compare_expr(self, expr: p.CompareExpr) -> None:
        self._write_line("CompareExpr")
        with self._child_level():
            self._write_line("left")
            with self._child_level(single=True):
                expr.left.accept(self)

            self._write_line(f"operator: {expr.operator.__class__.__name__}")

            self._write_line("right", last=True)
            with self._child_level(single=True):
                expr.right.accept(self)

    def visit_unary_expr(self, expr: p.UnaryExpr) -> None:
        self._write_line("UnaryExpr")
        with self._child_level():
            self._write_line(f"operator: {expr.operator.__class__.__name__}")

            self._write_line("right", last=True)
            with self._child_level(single=True):
                expr.right.accept(self)

    def visit_call_expr(self, expr: p.CallExpr) -> None:
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

    def visit_get_expr(self, expr: p.GetExpr) -> None:
        self._write_line("GetExpr")
        with self._child_level():
            self._write_line("object")
            with self._child_level(single=True):
                expr.object.accept(self)
            self._write_line(f"name: {expr.name}", last=True)

    def visit_literal_expr(self, expr: p.LiteralExpr) -> None:
        self._write_line("LiteralExpr")
        with self._child_level(single=True):
            self._write_line(f"value: {expr.value!r}")

    def visit_variable_expr(self, expr: p.VariableExpr) -> None:
        self._write_line("VariableExpr")
        with self._child_level(single=True):
            self._write_line(f"name: {expr.name}")

    def visit_logical_expr(self, expr: p.LogicalExpr) -> None:
        self._write_line("LogicalExpr")
        with self._child_level():
            self._write_line("left")
            with self._child_level(single=True):
                expr.left.accept(self)

            self._write_line(f"operator: {expr.operator.__class__.__name__}")

            self._write_line("right", last=True)
            with self._child_level(single=True):
                expr.right.accept(self)

    def visit_cast_expr(self, expr: p.CastExpr) -> None:
        self._write_line("CastExpr")
        with self._child_level():
            self._write_line("type")
            with self._child_level(single=True):
                expr.type.accept(self)
            self._write_line("expr")
            with self._child_level(single=True):
                expr.expr.accept(self)
            self._write_line(f"unsafe: {expr.unsafe}", last=True)

    def visit_ternary_expr(self, expr: p.TernaryExpr) -> None:
        self._write_line("TernaryExpr")
        with self._child_level():
            self._write_line("test")
            with self._child_level(single=True):
                expr.test.accept(self)

            self._write_line("if_true")
            with self._child_level(single=True):
                expr.if_true.accept(self)

            self._write_line("if_false", last=True)
            with self._child_level(single=True):
                expr.if_false.accept(self)

    def visit_list_expr(self, expr: p.ListExpr) -> None:
        self._write_line("ListExpr")
        with self._child_level():
            self._write_sequence("items", expr.items, last=True)

    def visit_dict_expr(self, expr: p.DictExpr) -> None:
        self._write_line("DictExpr")
        with self._child_level():
            self._write_sequence(
                "keys",
                expr.keys,
                print_func=lambda k: (
                    self._write_line("None") if k is None else k.accept(self)
                ),
            )
            self._write_sequence("values", expr.values, last=True)

    def visit_subscript_expr(self, expr: p.SubscriptExpr) -> None:
        self._write_line("SubscriptExpr")
        with self._child_level():
            self._write_line("object")
            with self._child_level(single=True):
                expr.object.accept(self)
            self._write_line("index", last=True)
            with self._child_level(single=True):
                expr.index.accept(self)

    def visit_slice_expr(self, expr: p.SliceExpr) -> None:
        self._write_line("SliceExpr")
        with self._child_level():
            self._write_optional_child("lower", expr.lower)
            self._write_optional_child("upper", expr.upper)
            self._write_optional_child("step", expr.step, last=True)

    def visit_tuple_expr(self, expr: p.TupleExpr) -> None:
        self._write_line("TupleExpr")
        with self._child_level():
            self._write_sequence("items", expr.items, last=True)

    def visit_raw_expr(self, expr: p.RawExpr) -> None:
        self._write_line("RawExpr")
        with self._child_level(single=True):
            self._write_line(f"expr: {ast.unparse(expr.expr)}")
