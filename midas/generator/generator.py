import ast
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, assert_never

import midas.ast.midas as m
import midas.ast.python as p
from midas.ast.location import Location
from midas.ast.printer import MidasPrinter
from midas.checker.checker import TypeChecker
from midas.checker.registry import TypesRegistry
from midas.checker.types import (
    AppliedType,
    BaseType,
    ColumnGroupBy,
    ColumnType,
    ComplexType,
    ConstraintType,
    DataFrameType,
    DerivedType,
    ExtensionType,
    FrameGroupBy,
    Function,
    GenericType,
    OverloadedFunction,
    TopType,
    TupleType,
    Type,
    TypeVar,
    UnitType,
    UnknownType,
)
from midas.generator.collector import Assertion, AssertionCollector
from midas.generator.constraints import ConstraintGenerator
from midas.generator.stubs import StubsGenerator
from midas.utils import TypedAST


@dataclass
class Scope:
    pre_assertions: list[ast.stmt] = field(default_factory=list[ast.stmt])
    aliases: list[str] = field(default_factory=list[str])


class Generator(p.Stmt.Visitor[ast.stmt], p.Expr.Visitor[ast.expr]):
    IS_DATAFRAME_FUNC = "__midas_is_dataframe__"
    IS_COLUMN_FUNC = "__midas_is_column__"

    def __init__(self, workdir: Path, types: TypesRegistry) -> None:
        self.workdir: Path = workdir.resolve()
        self.build_dir: Path = self.workdir / "build" / "midas"
        self.rel_src_path: Path = Path()
        self.logger: logging.Logger = logging.getLogger("Generator")

        self._typed_ast: TypedAST = TypedAST(
            stmts=[],
            judgements=[],
            evaluated_casts=[],
            assertions=AssertionCollector(),
        )
        self._alias_count: int = 0
        self._predicate_count: int = 0
        self._scopes: list[Scope] = []
        self._aliases: list[tuple[p.Expr, ast.expr]] = []

        self._constraint_generator: ConstraintGenerator = ConstraintGenerator(types)
        self._constraints: list[tuple[m.Expr, ast.expr]] = []

        self.define_is_dataframe: bool = False
        self.define_is_column: bool = False

    def set_src_path(self, path: Path):
        self.rel_src_path = path.resolve().relative_to(self.workdir)

    def generate_ast(self, typed_ast: TypedAST) -> ast.AST:
        self._typed_ast = typed_ast
        body: list[ast.stmt] = self._visit_body(typed_ast.stmts, can_be_empty=True)
        predicates: list[ast.stmt] = self._constraint_generator.get_definitions()

        body = predicates + body

        if self.define_is_dataframe:
            body = [self._is_dataframe_definition()] + body

        if self.define_is_column:
            body = [self._is_column_definition()] + body

        module = ast.Module(body=body, type_ignores=[])
        module = ast.fix_missing_locations(module)
        return module

    def generate(
        self,
        typed_ast: TypedAST,
        src_path: Path,
        out_path: Optional[Path] = None,
        type_files: Optional[list[tuple[Path, Optional[str]]]] = None,
    ) -> Path:
        self.set_src_path(src_path)
        if out_path is None:
            if self.build_dir.exists():
                shutil.rmtree(self.build_dir)
            self.build_dir.mkdir(parents=True, exist_ok=True)
            out_path = (self.build_dir / self.rel_src_path).resolve()
            try:
                _ = out_path.relative_to(self.build_dir)
            except ValueError:
                raise ValueError(
                    f"Directory traversal, {self.rel_src_path} points outside of parent directory"
                )
        out_dir: Path = out_path.parent
        out_dir.parent.mkdir(parents=True, exist_ok=True)

        if type_files is not None:
            for in_path, out_name in type_files:
                if out_name is None:
                    out_name = in_path.stem
                self.generate_stubs(in_path, out_dir / f"{out_name}.py")

        module: ast.AST = self.generate_ast(typed_ast)
        compiled: str = ast.unparse(module)

        out_path.write_text(compiled)
        return out_path

    def generate_stubs(self, in_path: Path, out_path: Path):
        checker = TypeChecker()
        checker.import_midas(in_path)
        generator = StubsGenerator(checker.types)
        module: ast.Module = generator.generate_stubs()
        module = ast.fix_missing_locations(module)
        output: str = ast.unparse(module)
        out_path.write_text(output)

    def convert(self, expr: p.Expr) -> ast.expr:
        for expr2, alias in self._aliases:
            if expr2 == expr:
                return alias
        assertions = self._typed_ast.assertions.get_assertions_for(expr)
        if len(assertions) != 0:
            return self._apply_assertions(expr, assertions)
        return expr.accept(self)

    def visit_binary_expr(self, expr: p.BinaryExpr) -> ast.expr:
        return ast.BinOp(
            left=self.convert(expr.left),
            op=expr.operator,
            right=self.convert(expr.right),
        )

    def visit_compare_expr(self, expr: p.CompareExpr) -> ast.expr:
        return ast.Compare(
            left=self.convert(expr.left),
            ops=[expr.operator],
            comparators=[self.convert(expr.right)],
        )

    def visit_unary_expr(self, expr: p.UnaryExpr) -> ast.expr:
        return ast.UnaryOp(
            op=expr.operator,
            operand=self.convert(expr.right),
        )

    def visit_call_expr(self, expr: p.CallExpr) -> ast.expr:
        return ast.Call(
            func=self.convert(expr.callee),
            args=[self.convert(arg) for arg in expr.arguments],
            keywords=[
                ast.keyword(arg=name, value=self.convert(arg))
                for name, arg in expr.keywords.items()
            ],
        )

    def visit_get_expr(self, expr: p.GetExpr) -> ast.expr:
        return ast.Attribute(
            value=self.convert(expr.object),
            attr=expr.name,
        )

    def visit_literal_expr(self, expr: p.LiteralExpr) -> ast.expr:
        return ast.Constant(value=expr.value)

    def visit_variable_expr(self, expr: p.VariableExpr) -> ast.expr:
        return ast.Name(id=expr.name)

    def visit_logical_expr(self, expr: p.LogicalExpr) -> ast.expr:
        return ast.BoolOp(
            op=expr.operator,
            values=[self.convert(expr.left), self.convert(expr.right)],
        )

    def visit_cast_expr(self, expr: p.CastExpr) -> ast.expr:
        expr2: ast.expr = self.convert(expr.expr)

        if expr in self._typed_ast.evaluated_casts or expr.unsafe:
            return expr2

        alias: ast.expr = self._make_alias(expr.expr, expr2)

        type: Type = self._get_expr_type(expr)
        asserts: list[ast.stmt] = self._make_cast_asserts(expr.location, alias, type)
        for assert_ in asserts:
            self._add_assert(assert_)

        return alias

    def visit_ternary_expr(self, expr: p.TernaryExpr) -> ast.expr:
        return ast.IfExp(
            test=self.convert(expr.test),
            body=self.convert(expr.if_true),
            orelse=self.convert(expr.if_false),
        )

    def visit_list_expr(self, expr: p.ListExpr) -> ast.expr:
        return ast.List(
            elts=[self.convert(item) for item in expr.items],
        )

    def visit_dict_expr(self, expr: p.DictExpr) -> ast.expr:
        return ast.Dict(
            keys=[self.convert(key) if key is not None else None for key in expr.keys],
            values=[self.convert(value) for value in expr.values],
        )

    def visit_subscript_expr(self, expr: p.SubscriptExpr) -> ast.expr:
        return ast.Subscript(
            value=self.convert(expr.object),
            slice=self.convert(expr.index),
        )

    def visit_slice_expr(self, expr: p.SliceExpr) -> ast.expr:
        return ast.Slice(
            lower=self.convert(expr.lower) if expr.lower is not None else None,
            upper=self.convert(expr.upper) if expr.upper is not None else None,
            step=self.convert(expr.step) if expr.step is not None else None,
        )

    def visit_tuple_expr(self, expr: p.TupleExpr) -> ast.expr:
        return ast.Tuple(
            elts=[self.convert(item) for item in expr.items],
        )

    def visit_raw_expr(self, expr: p.RawExpr) -> ast.expr:
        return expr.expr

    def visit_expression_stmt(self, stmt: p.ExpressionStmt) -> ast.stmt:
        return ast.Expr(
            value=self.convert(stmt.expr),
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
                    self.convert(arg.default)
                    for arg in stmt.posonlyargs + stmt.args
                    if arg.default is not None
                ],
                kw_defaults=[
                    self.convert(arg.default) if arg.default is not None else None
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
            targets=[self.convert(target) for target in stmt.targets],
            value=self.convert(stmt.value),
        )

    def visit_return_stmt(self, stmt: p.ReturnStmt) -> ast.stmt:
        return ast.Return(
            value=self.convert(stmt.value) if stmt.value is not None else None,
        )

    def visit_if_stmt(self, stmt: p.IfStmt) -> ast.stmt:
        return ast.If(
            test=self.convert(stmt.test),
            body=self._visit_body(stmt.body),
            orelse=self._visit_body(stmt.orelse, can_be_empty=True),
        )

    def visit_pass(self, stmt: p.Pass) -> ast.stmt:
        return ast.Pass()

    def visit_for_stmt(self, stmt: p.ForStmt) -> ast.stmt:
        return ast.For(
            target=self.convert(stmt.target),
            iter=self.convert(stmt.iterator),
            body=self._visit_body(stmt.body),
            orelse=[],
        )

    def visit_raw_stmt(self, stmt: p.RawStmt) -> ast.stmt:
        return stmt.stmt

    def _visit_body(
        self, stmts: list[p.Stmt], can_be_empty: bool = False
    ) -> list[ast.stmt]:
        generated: list[ast.stmt] = []
        for stmt in stmts:
            scope = Scope()
            self._scopes.append(scope)

            stmt2 = stmt.accept(self)
            generated.extend(scope.pre_assertions)
            generated.append(stmt2)
            if len(scope.aliases) != 0:
                generated.append(
                    ast.Delete(targets=[ast.Name(id=alias) for alias in scope.aliases])
                )
            self._scopes.pop()

        # Remove redundant pass statements
        if len(generated) > 1:
            generated = [stmt for stmt in generated if not isinstance(stmt, ast.Pass)]
        if len(generated) == 0 and not can_be_empty:
            generated = [ast.Pass()]
        return generated

    def _make_alias(self, node: p.Expr, expr: ast.expr) -> ast.expr:
        name: str = f"__midas_a{self._alias_count}__"
        alias = ast.Name(id=name)
        self._alias_count += 1
        self._scopes[-1].aliases.append(name)
        self._scopes[-1].pre_assertions.append(
            ast.Assign(
                targets=[alias],
                value=expr,
            )
        )
        self._aliases.append((node, alias))
        return alias

    def _build_assert(self, expr: ast.expr, message: str | ast.expr) -> ast.stmt:
        if isinstance(message, str):
            message = ast.Constant(value=message)
        return ast.Assert(
            test=expr,
            msg=message,
        )

    def _add_assert(self, assertion: ast.stmt):
        self._scopes[-1].pre_assertions.append(assertion)

    def _get_expr_type(self, query: p.Expr) -> Type:
        for expr, type in self._typed_ast.judgements:
            if expr == query:
                return type
        raise RuntimeError(f"Cannot get type judgement for {query}")

    def _make_cast_asserts(
        self, src_location: Location, expr: ast.expr, type: Type
    ) -> list[ast.stmt]:
        match type:
            case UnknownType() | TopType():
                return []

            case BaseType(name=name):
                return [
                    self._build_assert(
                        ast.Call(
                            func=ast.Name(id="isinstance"),
                            args=[expr, ast.Name(id=name)],
                            keywords=[],
                        ),
                        self._make_cast_assert_message(src_location, expr, type),
                    )
                ]

            case DerivedType(type=base):
                return self._make_cast_asserts(src_location, expr, base)

            case UnitType():
                return [
                    self._build_assert(
                        ast.Compare(
                            left=expr,
                            ops=[ast.Is()],
                            comparators=[
                                ast.Constant(value=None),
                            ],
                        ),
                        self._make_cast_assert_message(src_location, expr, type),
                    ),
                ]

            case AppliedType(body=body):
                return self._make_cast_asserts(src_location, expr, body)

            case ConstraintType(type=base, constraint=constraint):
                asserts: list[ast.stmt] = self._make_cast_asserts(
                    src_location, expr, base
                )
                asserts.append(
                    self._make_constraint_assert(src_location, expr, constraint)
                )
                return asserts

            case TypeVar(bound=bound):
                # TODO: check with type from arguments / use call-site context
                if bound is None:
                    return []
                return self._make_cast_asserts(src_location, expr, bound)

            case TupleType(items=items):
                asserts: list[ast.stmt] = [
                    self._build_assert(
                        ast.Call(
                            func=ast.Name(id="isinstance"),
                            args=[expr, ast.Name(id="tuple")],
                            keywords=[],
                        ),
                        self._make_cast_assert_message(src_location, expr, type),
                    ),
                ]
                assert isinstance(expr, ast.Tuple)
                for item, item_type in zip(expr.elts, items):
                    asserts.extend(
                        self._make_cast_asserts(src_location, item, item_type)
                    )
                return asserts

            case DataFrameType(columns=columns):
                self.define_is_dataframe = True
                asserts: list[ast.stmt] = [
                    self._build_assert(
                        ast.Call(
                            func=ast.Name(id=self.IS_DATAFRAME_FUNC),
                            args=[expr],
                            keywords=[],
                        ),
                        self._make_cast_assert_message(
                            src_location, expr, type, ": Not a dataframe"
                        ),
                    ),
                ]
                for column in columns:
                    asserts.append(
                        self._build_assert(
                            ast.Compare(
                                left=ast.Constant(value=column.name),
                                ops=[ast.In()],
                                comparators=[expr],
                            ),
                            self._make_cast_assert_message(
                                src_location,
                                expr,
                                type,
                                f": Missing column {column.name}",
                            ),
                        )
                    )
                    asserts.extend(
                        self._make_cast_asserts(
                            src_location,
                            ast.Subscript(
                                value=expr, slice=ast.Constant(value=column.name)
                            ),
                            column.type,
                        )
                    )
                return asserts

            case ColumnType():
                self.define_is_column = True
                asserts: list[ast.stmt] = [
                    self._build_assert(
                        ast.Call(
                            func=ast.Name(id=self.IS_COLUMN_FUNC),
                            args=[expr],
                            keywords=[],
                        ),
                        self._make_cast_assert_message(
                            src_location, expr, type, ": Not a column"
                        ),
                    ),
                ]
                inner_assert: Optional[ast.stmt] = self._make_column_inner_assert(
                    src_location, expr, type
                )
                if inner_assert is not None:
                    asserts.append(inner_assert)
                return asserts

            case (
                Function()
                | OverloadedFunction()
                | ComplexType()
                | ExtensionType()
                | GenericType()
                | FrameGroupBy()
                | ColumnGroupBy()
            ):
                self.logger.warning(f"Can't make assertion for type {type}")
                return []

            # Ensure exhaustiveness
            case _:
                assert_never(type)

    def _make_cast_assert_message(
        self,
        location: Location,
        expr: ast.expr,
        type: Type,
        extra: Optional[str] = None,
    ) -> ast.expr:
        loc_str: str = f"{self.rel_src_path}:L{location.lineno}:{location.col_offset+1}"
        # f"file.py:L1:1: CastError: Cannot cast {type(expr).__name__} to Type"
        return ast.JoinedStr(
            values=[
                ast.Constant(f"{loc_str}: CastError: Cannot cast "),
                ast.FormattedValue(
                    value=ast.Attribute(
                        value=ast.Call(
                            func=ast.Name(id="type"),
                            args=[expr],
                            keywords=[],
                        ),
                        attr="__name__",
                    ),
                    conversion=-1,
                ),
                ast.Constant(f" to {type}{extra or ''}"),
            ]
        )

    def _make_constraint_assert(
        self, src_location: Location, expr: ast.expr, constraint: m.Expr
    ) -> ast.stmt:
        test_func: ast.expr = self._get_constraint(constraint)
        return self._build_assert(
            ast.Call(
                func=test_func,
                args=[expr],
                keywords=[],
            ),
            self._make_constraint_assert_message(src_location, expr, constraint),
        )

    def _make_constraint_assert_message(
        self, location: Location, expr: ast.expr, constraint: m.Expr
    ) -> ast.expr:
        printer = MidasPrinter()
        constraint_str: str = printer.print(constraint)
        loc_str: str = f"{self.rel_src_path}:L{location.lineno}:{location.col_offset+1}"
        # f"file.py:L1:1: ConstraintError: Value does not fit constraint 'v > 0'"
        return ast.Constant(
            f"{loc_str}: ConstraintError: Value does not fit constraint '{constraint_str}'"
        )

    def _get_constraint(self, expr: m.Expr) -> ast.expr:
        for expr2, constraint in self._constraints:
            if expr2 == expr:
                return constraint

        constraint: ast.expr = self._constraint_generator.generate(expr)
        self._constraints.append((expr, constraint))
        return constraint

    def _is_dataframe_definition(self) -> ast.stmt:
        """
        def IS_DATAFRAME_FUNC(obj) -> bool:
            import pandas as pd
            return isinstance(obj, pd.DataFrame)
        """

        return ast.FunctionDef(
            name=self.IS_DATAFRAME_FUNC,
            args=ast.arguments(
                posonlyargs=[ast.arg(arg="obj")],
                args=[],
                kwonlyargs=[],
                defaults=[],
                kw_defaults=[],
            ),
            body=[
                ast.Import(names=[ast.alias(name="pandas", asname="pd")]),
                ast.Return(
                    value=ast.Call(
                        func=ast.Name(id="isinstance"),
                        args=[
                            ast.Name(id="obj"),
                            ast.Attribute(
                                value=ast.Name(id="pd"),
                                attr="DataFrame",
                            ),
                        ],
                        keywords=[],
                    )
                ),
            ],
            decorator_list=[],
            returns=ast.Name(id="bool"),
        )

    def _is_column_definition(self) -> ast.stmt:
        """
        def IS_COLUMN_FUNC(obj) -> bool:
            import pandas as pd
            return isinstance(obj, pd.Series)
        """

        return ast.FunctionDef(
            name=self.IS_COLUMN_FUNC,
            args=ast.arguments(
                posonlyargs=[ast.arg(arg="obj")],
                args=[],
                kwonlyargs=[],
                defaults=[],
                kw_defaults=[],
            ),
            body=[
                ast.Import(names=[ast.alias(name="pandas", asname="pd")]),
                ast.Return(
                    value=ast.Call(
                        func=ast.Name(id="isinstance"),
                        args=[
                            ast.Name(id="obj"),
                            ast.Attribute(
                                value=ast.Name(id="pd"),
                                attr="Series",
                            ),
                        ],
                        keywords=[],
                    )
                ),
            ],
            decorator_list=[],
            returns=ast.Name(id="bool"),
        )

    def _make_column_inner_assert(
        self, src_location: Location, column: ast.expr, type: ColumnType
    ) -> Optional[ast.stmt]:
        # TODO: improve message, maybe chain contexts
        col: ast.expr = ast.Name(id="col")
        body: list[ast.stmt] = self._make_cast_asserts(src_location, col, type.type)
        if len(body) == 0:
            return None
        return ast.For(
            target=col,
            iter=column,
            body=body,
            orelse=[],
        )

    def _convert_assertion(self, assertion: Assertion) -> ast.stmt:
        inputs: list[ast.expr] = []

        for input in assertion.inputs:
            converted: ast.expr = self.convert(input)
            alias: ast.expr = self._make_alias(input, converted)
            inputs.append(alias)

        test: ast.expr = assertion.builder(*inputs)
        location: Location = assertion.bound_expr.location
        loc_str: str = f"{self.rel_src_path}:L{location.lineno}:{location.col_offset+1}"
        return self._build_assert(
            test, f"{loc_str}: AssertionError: {assertion.message}"
        )

    def _apply_assertions(self, expr: p.Expr, assertions: list[Assertion]) -> ast.expr:
        for assertion in assertions:
            assert_stmt: ast.stmt
            assert_stmt = self._convert_assertion(assertion)
            self._add_assert(assert_stmt)

            # Mutating list in frozen dataclass
            # Not ideal but easiest way to avoid duplicate assertions
            self._typed_ast.assertions.remove(assertion)

        return expr.accept(self)
