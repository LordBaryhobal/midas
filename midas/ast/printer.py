from __future__ import annotations

import ast
import io
from contextlib import contextmanager
from enum import Enum, auto
from typing import Generator, Generic, Optional, Protocol, TypeVar

import midas.ast.midas as m
import midas.ast.python as p


class _Level(Enum):
    EMPTY = auto()
    ACTIVE = auto()
    LAST = auto()


class Expr(Protocol):
    def accept(self, printer: AstPrinter) -> None: ...


T = TypeVar("T", bound=Expr)


class AstPrinter(Generic[T]):
    LAST_CHILD = "└── "
    CHILD = "├── "
    VERTICAL = "│   "
    EMPTY = "    "

    def __init__(self):
        self._levels: list[_Level] = []
        self._idx: Optional[int] = None
        self._buf: io.StringIO = io.StringIO()

    def print(self, expr: T):
        self._buf = io.StringIO()
        expr.accept(self)
        return self._buf.getvalue()

    @contextmanager
    def _child_level(self, single: bool = False) -> Generator[None, None, None]:
        self._levels.append(_Level.LAST if single else _Level.ACTIVE)
        try:
            yield
        finally:
            self._levels.pop()

    def _mark_last(self):
        if self._levels:
            self._levels[-1] = _Level.LAST

    def _write_line(self, text: str, *, last: bool = False):
        if last:
            self._mark_last()
        indent: str = self._build_indent()
        if self._idx is not None:
            text = f"[{self._idx}] {text}"
            self._idx = None
        self._buf.write(indent + text + "\n")

    def _build_indent(self) -> str:
        parts: list[str] = []
        for level in self._levels[:-1]:
            parts.append(self.EMPTY if level == _Level.EMPTY else self.VERTICAL)
        if self._levels:
            if self._levels[-1] == _Level.LAST:
                parts.append(self.LAST_CHILD)
                self._levels[-1] = _Level.EMPTY
            else:
                parts.append(self.CHILD)
        return "".join(parts)

    def _write_optional_child(
        self, label: str, child: Optional[T], *, last: bool = False
    ):
        if last:
            self._mark_last()
        if child is None:
            self._write_line(f"{label}: None")
        else:
            self._write_line(label)
            with self._child_level(single=True):
                child.accept(self)


class MidasAstPrinter(
    AstPrinter, m.Expr.Visitor[None], m.Stmt.Visitor[None], m.Type.Visitor[None]
):
    # Statements

    def visit_type_stmt(self, stmt: m.TypeStmt) -> None:
        self._write_line("TypeStmt")
        with self._child_level():
            self._write_line(f'name: "{stmt.name.lexeme}"')
            self._write_line("params")
            with self._child_level():
                for i, param in enumerate(stmt.params):
                    self._idx = i
                    if i == len(stmt.params) - 1:
                        self._mark_last()
                    self._print_type_param(param)
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
            self._write_line("params")
            with self._child_level():
                for i, param in enumerate(stmt.params):
                    self._idx = i
                    if i == len(stmt.params) - 1:
                        self._mark_last()
                    self._print_type_param(param)
            self._write_line(f'name: "{stmt.name.lexeme}"')
            self._write_line("params")
            with self._child_level():
                for i, param in enumerate(stmt.params):
                    self._idx = i
                    if i == len(stmt.params) - 1:
                        self._mark_last()
                    self._print_type_param(param)
            self._write_line("members", last=True)
            with self._child_level():
                for i, member in enumerate(stmt.members):
                    self._idx = i
                    if i == len(stmt.members) - 1:
                        self._mark_last()
                    member.accept(self)

    def visit_predicate_stmt(self, stmt: m.PredicateStmt):
        self._write_line("PredicateStmt")
        with self._child_level():
            self._write_line(f'name: "{stmt.name.lexeme}"')
            self._write_line("params")
            with self._child_level():
                for i, spec in enumerate(stmt.params):
                    self._idx = i
                    if i == len(stmt.params) - 1:
                        self._mark_last()
                    self._visit_param_spec(spec)

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
            self._write_line("arguments")
            with self._child_level():
                for i, arg in enumerate(expr.arguments):
                    self._idx = i
                    if i == len(expr.arguments) - 1:
                        self._mark_last()
                    arg.accept(self)
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
            self._write_line("args", last=True)
            with self._child_level():
                for i, param in enumerate(type.args):
                    self._idx = i
                    if i == len(type.args) - 1:
                        self._mark_last()
                    param.accept(self)

    def visit_constraint_type(self, type: m.ConstraintType) -> None:
        self._write_line("ConstraintType")
        with self._child_level():
            self._write_line("type")
            with self._child_level(single=True):
                type.type.accept(self)
            self._write_line("constraint", last=True)
            with self._child_level(single=True):
                type.constraint.accept(self)

    def visit_complex_type(self, type: m.ComplexType) -> None:
        self._write_line("ComplexType")
        with self._child_level():
            self._write_line("members", last=True)
            with self._child_level():
                for i, member in enumerate(type.members):
                    self._idx = i
                    if i == len(type.members) - 1:
                        self._mark_last()
                    member.accept(self)

    def visit_extension_type(self, type: m.ExtensionType) -> None:
        self._write_line("ExtensionType")
        with self._child_level():
            self._write_line("base")
            with self._child_level(single=True):
                type.base.accept(self)
            self._write_line("extension", last=True)
            with self._child_level(single=True):
                type.extension.accept(self)

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
            self._write_line("pos")
            with self._child_level():
                for i, arg in enumerate(spec.pos):
                    self._idx = i
                    if i == len(spec.pos) - 1:
                        self._mark_last()
                    self._print_function_arg(arg)

            self._write_line("mixed")
            with self._child_level():
                for i, arg in enumerate(spec.mixed):
                    self._idx = i
                    if i == len(spec.mixed) - 1:
                        self._mark_last()
                    self._print_function_arg(arg)

            self._write_line("kw", last=True)
            with self._child_level():
                for i, arg in enumerate(spec.kw):
                    self._idx = i
                    if i == len(spec.kw) - 1:
                        self._mark_last()
                    self._print_function_arg(arg)

    def _print_function_arg(self, arg: m.FunctionType.Argument) -> None:
        self._write_line("Argument")
        with self._child_level():
            name: str = "None"
            if arg.name is not None:
                name = f'"{arg.name.lexeme}"'
            self._write_line(f"name: {name}")
            self._write_line("type")
            with self._child_level(single=True):
                arg.type.accept(self)
            self._write_line(f"required: {arg.required}", last=True)


class MidasPrinter(m.Expr.Visitor[str], m.Stmt.Visitor[str], m.Type.Visitor[str]):
    def __init__(self, indent: int = 4):
        self.indent: int = indent
        self.level: int = 0

    def indented(self, text: str) -> str:
        return " " * (self.level * self.indent) + text

    def print(self, expr: m.Expr | m.Stmt | m.Type) -> str:
        self.level = 0
        return expr.accept(self)

    def visit_type_stmt(self, stmt: m.TypeStmt) -> str:
        template: str = ""
        if len(stmt.params) != 0:
            params: list[str] = [self._print_type_param(param) for param in stmt.params]
            template = f"[{', '.join(params)}]"
        res: str = f"type {stmt.name.lexeme}{template} = {stmt.type.accept(self)}"
        return self.indented(res)

    def _print_type_param(self, param: m.TypeParam) -> str:
        res: str = param.name.lexeme
        if param.bound is not None:
            res += "<:" + param.bound.accept(self)
        return res

    def visit_member_stmt(self, stmt: m.MemberStmt):
        keyword: str = {
            m.MemberKind.PROPERTY: "prop",
            m.MemberKind.METHOD: "def",
        }.get(stmt.kind, "")
        res: str = f"{keyword} {stmt.name.lexeme}: {stmt.type.accept(self)}"
        return self.indented(res)

    def visit_extend_stmt(self, stmt: m.ExtendStmt):
        template: str = ""
        if len(stmt.params) != 0:
            params: list[str] = [self._print_type_param(param) for param in stmt.params]
            template = f"[{', '.join(params)}]"
        res: str = self.indented(f"extend {stmt.name.lexeme}{template}")
        res += " {\n"
        self.level += 1
        for member in stmt.members:
            res += member.accept(self) + "\n"
        self.level -= 1
        res += self.indented("}")
        return res

    def visit_predicate_stmt(self, stmt: m.PredicateStmt):
        name: str = stmt.name.lexeme
        sig: str = "".join(self._visit_param_spec(spec) for spec in stmt.params)
        body: str = stmt.body.accept(self)
        return self.indented(f"predicate {name}{sig} = {body}")

    def visit_logical_expr(self, expr: m.LogicalExpr):
        left: str = expr.left.accept(self)
        operator: str = expr.operator.lexeme
        right: str = expr.right.accept(self)
        return f"{left} {operator} {right}"

    def visit_binary_expr(self, expr: m.BinaryExpr):
        left: str = expr.left.accept(self)
        operator: str = expr.operator.lexeme
        right: str = expr.right.accept(self)
        return f"{left} {operator} {right}"

    def visit_unary_expr(self, expr: m.UnaryExpr):
        operator: str = expr.operator.lexeme
        right: str = expr.right.accept(self)
        return f"{operator}{right}"

    def visit_call_expr(self, expr: m.CallExpr) -> str:
        args: list[str] = [arg.accept(self) for arg in expr.arguments] + [
            f"{name}={arg.accept(self)}" for name, arg in expr.keywords.items()
        ]
        return f"{expr.callee.accept(self)}({', '.join(args)})"

    def visit_get_expr(self, expr: m.GetExpr):
        expr_: str = expr.expr.accept(self)
        name: str = expr.name.lexeme
        return f"{expr_}.{name}"

    def visit_variable_expr(self, expr: m.VariableExpr):
        return expr.name.lexeme

    def visit_grouping_expr(self, expr: m.GroupingExpr):
        expr_: str = expr.expr.accept(self)
        return f"({expr_})"

    def visit_literal_expr(self, expr: m.LiteralExpr):
        return str(expr.value)

    def visit_wildcard_expr(self, expr: m.WildcardExpr):
        return "_"

    def visit_named_type(self, type: m.NamedType) -> str:
        return type.name.lexeme

    def visit_generic_type(self, type: m.GenericType) -> str:
        res: str = type.type.accept(self)
        if len(type.args) != 0:
            args: list[str] = [param.accept(self) for param in type.args]
            res += f"[{', '.join(args)}]"
        return res

    def visit_constraint_type(self, type: m.ConstraintType) -> str:
        res: str = type.type.accept(self)
        res += " where " + type.constraint.accept(self)
        return res

    def visit_complex_type(self, type: m.ComplexType) -> str:
        res: str = "{\n"
        self.level += 1
        for member in type.members:
            res += member.accept(self)
            res += "\n"
        self.level -= 1
        res += self.indented("}")
        return res

    def visit_extension_type(self, type: m.ExtensionType) -> str:
        return f"{type.base.accept(self)} & {type.extension.accept(self)}"

    def visit_function_type(self, type: m.FunctionType) -> str:
        spec: str = self._visit_param_spec(type.params)
        return f"fn {spec} -> {type.returns.accept(self)}"

    def _visit_param_spec(self, spec: m.ParamSpec) -> str:
        pos_args: list[str] = [self._print_arg(arg) for arg in spec.pos]
        mixed_args: list[str] = [self._print_arg(arg) for arg in spec.mixed]
        kw_args: list[str] = [self._print_arg(arg) for arg in spec.kw]
        args: list[str] = pos_args

        if len(pos_args) != 0:
            args.append("/")
        args += mixed_args
        if len(kw_args) != 0:
            args.append("*")
        args += kw_args
        return f"({', '.join(args)})"

    def _print_arg(self, arg: m.FunctionType.Argument) -> str:
        res: str = ""
        if arg.name is not None:
            res += arg.name.lexeme
            res += ": "
        res += arg.type.accept(self)
        if not arg.required:
            res += "?"
        return res


class PythonAstPrinter(
    AstPrinter,
    p.MidasType.Visitor[None],
    p.Stmt.Visitor[None],
    p.Expr.Visitor[None],
):
    def visit_base_type(self, node: p.BaseType) -> None:
        self._write_line("BaseType")
        with self._child_level():
            self._write_line(f"base: {node.base}")
            self._write_optional_child("param", node.param, last=True)

    def visit_constraint_type(self, node: p.ConstraintType) -> None:
        self._write_line("ConstraintType")
        with self._child_level():
            self._write_line("type")
            with self._child_level(single=True):
                node.type.accept(self)
            self._write_line(f"constraint: {ast.unparse(node.constraint)}", last=True)

    def visit_frame_column(self, node: p.FrameColumn) -> None:
        self._write_line("FrameColumn")
        with self._child_level():
            self._write_line(f"name: {node.name}")
            self._write_optional_child("type", node.type, last=True)

    def visit_frame_type(self, node: p.FrameType) -> None:
        self._write_line("FrameType")
        with self._child_level():
            self._write_line("columns", last=True)
            with self._child_level():
                for i, col in enumerate(node.columns):
                    self._idx = i
                    if i == len(node.columns) - 1:
                        self._mark_last()
                    col.accept(self)

    def visit_expression_stmt(self, stmt: p.ExpressionStmt) -> None:
        stmt.expr.accept(self)

    def visit_function(self, stmt: p.Function) -> None:
        self._write_line("Function")
        with self._child_level():
            self._write_line(f"name: {stmt.name}")

            self._write_line("posonlyargs")
            with self._child_level():
                for i, arg in enumerate(stmt.posonlyargs):
                    self._idx = i
                    if i == len(stmt.posonlyargs) - 1:
                        self._mark_last()
                    self._print_argument(arg)

            self._write_line("args")
            with self._child_level():
                for i, arg in enumerate(stmt.args):
                    self._idx = i
                    if i == len(stmt.args) - 1:
                        self._mark_last()
                    self._print_argument(arg)

            self._write_line("kwonlyargs")
            with self._child_level():
                for i, arg in enumerate(stmt.kwonlyargs):
                    self._idx = i
                    if i == len(stmt.kwonlyargs) - 1:
                        self._mark_last()
                    self._print_argument(arg)

            self._write_optional_child("returns", stmt.returns)
            self._write_line("body", last=True)
            with self._child_level():
                for i, body_stmt in enumerate(stmt.body):
                    self._idx = i
                    if i == len(stmt.body) - 1:
                        self._mark_last()
                    body_stmt.accept(self)

    def _print_argument(self, arg: p.Function.Argument) -> None:
        self._write_line("FunctionArgument")
        with self._child_level():
            self._write_line(f"name: {arg.name}")
            self._write_optional_child("type", arg.type, last=True)

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
            self._write_line("targets")
            with self._child_level():
                for i, target in enumerate(stmt.targets):
                    self._idx = i
                    if i == len(stmt.targets) - 1:
                        self._mark_last()
                    target.accept(self)
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
            self._write_line("body")
            with self._child_level():
                for i, body_stmt in enumerate(stmt.body):
                    self._idx = i
                    if i == len(stmt.body) - 1:
                        self._mark_last()
                    body_stmt.accept(self)
            self._write_line("orelse", last=True)
            with self._child_level():
                for i, else_stmt in enumerate(stmt.orelse):
                    self._idx = i
                    if i == len(stmt.orelse) - 1:
                        self._mark_last()
                    else_stmt.accept(self)

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
            self._write_line("body", last=True)
            with self._child_level():
                for i, body_stmt in enumerate(stmt.body):
                    self._idx = i
                    if i == len(stmt.body) - 1:
                        self._mark_last()
                    body_stmt.accept(self)

    def visit_raw_stmt(self, stmt: p.RawStmt) -> None:
        self._write_line("RawStmt")
        with self._child_level(single=True):
            self._write_line(f"stmt: {ast.unparse(stmt.stmt)}")

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

            self._write_line("arguments")
            with self._child_level():
                for i, arg in enumerate(expr.arguments):
                    self._idx = i
                    if i == len(expr.arguments) - 1:
                        self._mark_last()
                    arg.accept(self)

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
            self._write_line("items", last=True)
            with self._child_level():
                for i, item in enumerate(expr.items):
                    self._idx = i
                    if i == len(expr.items) - 1:
                        self._mark_last()
                    item.accept(self)

    def visit_dict_expr(self, expr: p.DictExpr) -> None:
        self._write_line("DictExpr")
        with self._child_level():
            self._write_line("keys")
            with self._child_level():
                for i, key in enumerate(expr.keys):
                    self._idx = i
                    if i == len(expr.keys) - 1:
                        self._mark_last()
                    if key is None:
                        self._write_line("None")
                    else:
                        key.accept(self)
            self._write_line("values", last=True)
            with self._child_level():
                for i, value in enumerate(expr.values):
                    self._idx = i
                    if i == len(expr.values) - 1:
                        self._mark_last()
                    value.accept(self)

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

    def visit_raw_expr(self, expr: p.RawExpr) -> None:
        self._write_line("RawExpr")
        with self._child_level(single=True):
            self._write_line(f"expr: {ast.unparse(expr.expr)}")
