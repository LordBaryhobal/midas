import ast
import shutil
from pathlib import Path

import midas.ast.python as p
from midas.utils import TypedAST


class Generator(p.Stmt.Visitor[ast.stmt], p.Expr.Visitor[ast.expr]):
    def __init__(self, workdir: Path) -> None:
        self.workdir: Path = workdir.resolve()
        self.build_dir: Path = self.workdir / "build" / "midas"
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
        self.build_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, typed_ast: TypedAST, src_path: Path) -> Path:
        body: list[ast.stmt] = self._visit_body(typed_ast.stmts)
        module = ast.Module(body=body, type_ignores=[])
        module = ast.fix_missing_locations(module)
        compiled: str = ast.unparse(module)
        rel_src_path: Path = src_path.relative_to(self.workdir)
        out_path: Path = (self.build_dir / rel_src_path).resolve()
        try:
            _ = out_path.relative_to(self.build_dir)
        except ValueError:
            raise ValueError(
                f"Directory traversal, {rel_src_path} points outside of parent directory"
            )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(compiled)
        return out_path

    def visit_binary_expr(self, expr: p.BinaryExpr) -> ast.expr:
        return ast.BinOp(
            left=expr.left.accept(self),
            op=expr.operator,
            right=expr.right.accept(self),
        )

    def visit_compare_expr(self, expr: p.CompareExpr) -> ast.expr:
        return ast.Compare(
            left=expr.left.accept(self),
            ops=[expr.operator],
            comparators=[expr.right.accept(self)],
        )

    def visit_unary_expr(self, expr: p.UnaryExpr) -> ast.expr:
        return ast.UnaryOp(
            op=expr.operator,
            operand=expr.right.accept(self),
        )

    def visit_call_expr(self, expr: p.CallExpr) -> ast.expr:
        return ast.Call(
            func=expr.callee.accept(self),
            args=[arg.accept(self) for arg in expr.arguments],
            keywords=[
                ast.keyword(arg=name, value=arg.accept(self))
                for name, arg in expr.keywords.items()
            ],
        )

    def visit_get_expr(self, expr: p.GetExpr) -> ast.expr:
        return ast.Attribute(
            value=expr.object.accept(self),
            attr=expr.name,
        )

    def visit_literal_expr(self, expr: p.LiteralExpr) -> ast.expr:
        return ast.Constant(value=expr.value)

    def visit_variable_expr(self, expr: p.VariableExpr) -> ast.expr:
        return ast.Name(id=expr.name)

    def visit_logical_expr(self, expr: p.LogicalExpr) -> ast.expr:
        return ast.BoolOp(
            op=expr.operator,
            values=[expr.left.accept(self), expr.right.accept(self)],
        )

    def visit_cast_expr(self, expr: p.CastExpr) -> ast.expr:
        # TODO: insert assertion
        return expr.expr.accept(self)

    def visit_ternary_expr(self, expr: p.TernaryExpr) -> ast.expr:
        return ast.IfExp(
            test=expr.test.accept(self),
            body=expr.if_true.accept(self),
            orelse=expr.if_false.accept(self),
        )

    def visit_list_expr(self, expr: p.ListExpr) -> ast.expr:
        return ast.List(
            elts=[item.accept(self) for item in expr.items],
        )

    def visit_subscript_expr(self, expr: p.SubscriptExpr) -> ast.expr:
        return ast.Subscript(
            value=expr.object.accept(self),
            slice=expr.index.accept(self),
        )

    def visit_slice_expr(self, expr: p.SliceExpr) -> ast.expr:
        return ast.Slice(
            lower=expr.lower.accept(self) if expr.lower is not None else None,
            upper=expr.upper.accept(self) if expr.upper is not None else None,
            step=expr.step.accept(self) if expr.step is not None else None,
        )

    def visit_expression_stmt(self, stmt: p.ExpressionStmt) -> ast.stmt:
        return ast.Expr(
            value=stmt.expr.accept(self),
        )

    def visit_function(self, stmt: p.Function) -> ast.stmt:
        return ast.FunctionDef(
            name=stmt.name,
            args=ast.arguments(
                posonlyargs=[ast.arg(arg=arg.name) for arg in stmt.posonlyargs],
                vararg=None,
                args=[ast.arg(arg=arg.name) for arg in stmt.args],
                kwonlyargs=[ast.arg(arg=arg.name) for arg in stmt.kwonlyargs],
                kwarg=None,
                defaults=[
                    arg.default.accept(self)
                    for arg in stmt.posonlyargs + stmt.args
                    if arg.default is not None
                ],
                kw_defaults=[
                    arg.default.accept(self) if arg.default is not None else None
                    for arg in stmt.kwonlyargs
                ],
            ),
            body=self._visit_body(stmt.body),
            decorator_list=[],
        )

    def visit_type_assign(self, stmt: p.TypeAssign) -> ast.stmt:
        # TODO: is that ok?
        return ast.Pass()

    def visit_assign_stmt(self, stmt: p.AssignStmt) -> ast.stmt:
        return ast.Assign(
            targets=[target.accept(self) for target in stmt.targets],
            value=stmt.value.accept(self),
        )

    def visit_return_stmt(self, stmt: p.ReturnStmt) -> ast.stmt:
        return ast.Return(
            value=stmt.value.accept(self) if stmt.value is not None else None,
        )

    def visit_if_stmt(self, stmt: p.IfStmt) -> ast.stmt:
        return ast.If(
            test=stmt.test.accept(self),
            body=self._visit_body(stmt.body),
            orelse=self._visit_body(stmt.orelse),
        )

    def visit_pass(self, stmt: p.Pass) -> ast.stmt:
        return ast.Pass()

    def visit_for_stmt(self, stmt: p.ForStmt) -> ast.stmt:
        return ast.For(
            target=stmt.target.accept(self),
            iter=stmt.iterator.accept(self),
            body=self._visit_body(stmt.body),
            orelse=[],
        )

    def _visit_body(self, stmts: list[p.Stmt]) -> list[ast.stmt]:
        return [stmt.accept(self) for stmt in stmts]
