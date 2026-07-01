import ast
import logging
from dataclasses import dataclass
from typing import Any, Optional

import midas.ast.python as p
from midas.ast.location import Location
from midas.ast.printer import MidasPrinter
from midas.checker.dispatcher import CallDispatcher, CallResult
from midas.checker.environment import Environment
from midas.checker.evaluator import Evaluator
from midas.checker.frames import FrameManager
from midas.checker.operators import (
    PY_COMPARATOR_METHODS,
    PY_OPERATOR_METHODS,
    PY_UNARY_METHODS,
)
from midas.checker.preamble import Preamble
from midas.checker.registry import TypesRegistry
from midas.checker.reporter import FileReporter, Reporter
from midas.checker.resolver import Resolver
from midas.checker.types import (
    AppliedType,
    BaseType,
    ColumnType,
    ConstraintType,
    DataFrameType,
    DerivedType,
    Function,
    GenericType,
    TupleType,
    Type,
    TypeVar,
    UnitType,
    UnknownType,
    Variance,
    unfold_type,
)
from midas.parser.python import PythonParser
from midas.utils import TypedAST

TypedExpr = tuple[p.Expr, Type]


class ReturnException(Exception):
    pass


class UndefinedMethodException(Exception):
    pass


@dataclass(frozen=True, kw_only=True)
class MappedArgument:
    expr: p.Expr
    type: Type
    argument: Function.Argument


@dataclass(frozen=True, kw_only=True)
class OverloadCandidate:
    function: Function
    mapped: list[MappedArgument]


class PythonTyper(
    p.Stmt.Visitor[None],
    p.Expr.Visitor[Type],
    p.MidasType.Visitor[Type],
):
    """A type checker which can use custom type definitions"""

    def __init__(
        self,
        types: TypesRegistry,
        reporter: Reporter,
    ):
        self.logger: logging.Logger = logging.getLogger("PythonTyper")
        self.reporter: FileReporter = reporter.for_file(None)
        self.types: TypesRegistry = types
        self.frame_mgr: FrameManager = FrameManager(self)
        self.global_env: Environment = Preamble(self.types)
        self.env: Environment = self.global_env
        self.locals: dict[p.Expr, int] = {}
        self.judgements: list[tuple[p.Expr, Type]] = []
        self.evaluated_casts: list[p.CastExpr] = []
        self.dispatcher: CallDispatcher[p.Expr] = CallDispatcher[p.Expr](
            self.types, self.reporter
        )

    def set_reporter(self, reporter: FileReporter):
        self.reporter = reporter
        self.dispatcher.set_reporter(self.reporter)

    def process(self, source: str, path: Optional[str]) -> TypedAST:
        reporter: FileReporter = self.reporter.for_file(path)
        self.set_reporter(reporter)

        tree: ast.Module = ast.parse(source, filename=path or "<unknown>")
        parser = PythonParser()
        stmts: list[p.Stmt] = parser.parse_module(tree)
        resolver = Resolver()
        resolver.resolve(*stmts)

        self.env = self.global_env
        self.locals = resolver.locals
        self.judgements = []
        self.evaluated_casts = []

        self.check(stmts)

        return TypedAST(
            stmts=stmts,
            judgements=self.judgements,
            evaluated_casts=self.evaluated_casts,
        )

    def judge(self, expr: p.Expr, type: Type):
        """Record a typing judgement

        Args:
            expr (p.Expr): the judged expression
            type (Type): the type of the expression
        """
        self.judgements.append((expr, type))

    def compute_type(self, expr: p.Expr) -> Type:
        """Evaluate the type of an expression

        Args:
            expr (p.Expr): the expression to type

        Returns:
            Type: the type of the given expression
        """
        return expr.accept(self)

    def type_of(self, expr: p.Expr) -> Type:
        """Evaluate the type of an expression and record the judgement

        Args:
            expr (p.Expr): the expression to evaluate

        Returns:
            Type: the type of the given expression
        """
        type: Type = self.compute_type(expr)
        self.judge(expr, type)
        return type

    def resolve_type_expr(self, expr: p.MidasType) -> Type:
        return expr.accept(self)

    def process_stmt(self, stmt: p.Stmt) -> None:
        stmt.accept(self)

    def process_block(self, block: list[p.Stmt], env: Environment) -> bool:
        """Evaluate a sequence of statements

        Args:
            block (list[p.Stmt]): the statements to evaluate
            env (Environment): the environment in which to evaluate

        Returns:
            bool: whether a return statement is present in the block
        """
        previous_env: Environment = self.env
        self.env = env
        returned: bool = False
        for i, stmt in enumerate(block):
            try:
                self.process_stmt(stmt)
            except ReturnException:
                returned = True
                if i < len(block) - 1:
                    self.reporter.warning(
                        block[i + 1].location, "Unreachable statement"
                    )
                break
        self.env = previous_env
        return returned

    def check(self, statements: list[p.Stmt]) -> None:
        """Type check a sequence of statements and returns diagnostics

        Args:
            statements (list[p.Stmt]): the statements to evaluate and check
        """
        for stmt in statements:
            self.process_stmt(stmt)

        self.logger.debug(f"Final environment: {self.env.flat_dict()}")

    def look_up_variable(self, name: str, expr: p.Expr) -> Optional[Type]:
        """Look up a variable in the environment it was declared

        Args:
            name (str): the name of the variable
            expr (p.Expr): the variable expression, used to lookup the scope distance

        Returns:
            Optional[Type]: the type of the variable, or None if it was not found
        """
        distance: Optional[int] = self.locals.get(expr)
        if distance is not None:
            return self.env.get_at(distance, name)
        return self.global_env.get(name)

    def call_method(
        self,
        location: Location,
        obj: Type,
        method_name: str,
        positional: list[TypedExpr],
        keywords: dict[str, TypedExpr],
    ) -> Optional[Type]:
        unfolded: Type = unfold_type(obj)
        match unfolded:
            case DataFrameType():
                return self.frame_mgr.call(
                    method=method_name,
                    location=location,
                    frame=unfolded,
                    positional=positional,
                    keywords=keywords,
                )

        method: Optional[Type] = self.types.lookup_member(obj, method_name)
        if method is None:
            raise UndefinedMethodException

        result: CallResult = self.dispatcher.get_result(
            location=location,
            callee=method,
            positional=positional,
            keywords=keywords,
        )
        return result.result

    def is_subtype(self, type1: Type, type2: Type) -> bool:
        return self.types.is_subtype(type1, type2)

    def visit_expression_stmt(self, stmt: p.ExpressionStmt) -> None:
        self.type_of(stmt.expr)

    def visit_function(self, stmt: p.Function) -> None:
        env: Environment = Environment(self.env)
        pos_args: list[Function.Argument] = []
        args: list[Function.Argument] = []
        kw_args: list[Function.Argument] = []

        def eval_arg_type(arg: p.Function.Argument) -> Type:
            if arg.type is not None:
                return self.resolve_type_expr(arg.type)
            if arg.default is not None:
                return self.type_of(arg.default)
            return UnknownType()

        pos: int = 0
        for arg in stmt.posonlyargs:
            pos_args.append(
                Function.Argument(
                    pos=pos,
                    name=arg.name,
                    type=eval_arg_type(arg),
                    required=arg.default is None,
                )
            )
            pos += 1
        for arg in stmt.args:
            args.append(
                Function.Argument(
                    pos=pos,
                    name=arg.name,
                    type=eval_arg_type(arg),
                    required=arg.default is None,
                )
            )
            pos += 1
        for arg in stmt.kwonlyargs:
            kw_args.append(
                Function.Argument(
                    pos=pos,  # not relevant
                    name=arg.name,
                    type=eval_arg_type(arg),
                    required=arg.default is None,
                )
            )
            pos += 1

        all_args: list[Function.Argument] = pos_args + args + kw_args
        for arg in all_args:
            env.define(arg.name, arg.type)

        returns_hint: Optional[Type] = None
        if stmt.returns is not None:
            returns_hint = self.resolve_type_expr(stmt.returns)
            # Early define to handle simple fully-typed recursion
            inside_function: Function = Function(
                pos_args=pos_args,
                args=args,
                kw_args=kw_args,
                returns=returns_hint,
            )
            self.env.define(stmt.name, inside_function)

        returned: bool = self.process_block(stmt.body, env)
        inferred_return: Type = UnknownType()
        if not returned:
            env.return_types.append(UnitType())
        return_types: list[Type] = self.types.reduce_types(env.return_types)
        if len(return_types) == 1:
            inferred_return = return_types[0]
        elif len(return_types) > 1:
            self.reporter.error(
                stmt.location,
                f"Mixed return types: {return_types}",
            )

        returns: Type = UnknownType()
        if returns_hint is not None:
            assert stmt.returns is not None
            returns = returns_hint
            if not self.is_subtype(inferred_return, returns):
                self.reporter.error(
                    stmt.returns.location,
                    f"Return type mismatch, annotated {returns} but returns {inferred_return}",
                )
        else:
            returns = inferred_return

        # TODO: handle *args and **kwargs sinks
        function: Type = Function(
            pos_args=pos_args,
            args=args,
            kw_args=kw_args,
            returns=returns,
        )
        generic_params: list[TypeVar] = []
        all_types: list[Type] = [arg.type for arg in all_args] + [returns]
        for type in all_types:
            if isinstance(type, TypeVar):
                if type not in generic_params:
                    generic_params.append(type)

        if len(generic_params) != 0:
            function = GenericType(
                name=stmt.name,
                params=generic_params,
                body=function,
            )
        self.env.define(stmt.name, function)

    def visit_type_assign(self, stmt: p.TypeAssign) -> None:
        # TODO check not yet defined locally
        type: Type = self.resolve_type_expr(stmt.type)
        self.env.define(stmt.name, type)

    def visit_assign_stmt(self, stmt: p.AssignStmt) -> None:
        value_type: Type = self.type_of(stmt.value)
        for target in stmt.targets:
            self._assign(stmt.location, target, value_type)

    def _assign(self, location: Location, target: p.Expr, value_type: Type):
        match target:
            case p.VariableExpr():
                self._assign_var(location, target, value_type)

            # Allow any kind of object because we disallow creating new attributes
            case p.GetExpr(object=object, name=name):
                self._assign_attr(location, object, name, value_type)

            # Only support variable expressions because modifying
            # the underlying value would require reference types
            case p.SubscriptExpr(object=p.VariableExpr() as var, index=index):
                self._assign_sub(location, var, index, value_type)

            case _:
                if not isinstance(target, p.VariableExpr):
                    self.logger.warning(f"Unsupported assignment to {target}")
                    self.reporter.warning(
                        target.location, f"Unsupported assignment to {target}"
                    )

    def _assign_var(self, location: Location, target: p.VariableExpr, value_type: Type):
        name: str = target.name
        var_type: Optional[Type] = self.look_up_variable(name, target)

        if var_type is None:
            self.env.define(name, value_type)
        else:
            # S <: T
            # Γ, x: T   v: S
            # x = v
            if not self.is_subtype(value_type, var_type):
                self.reporter.error(
                    location,
                    f"Cannot assign {value_type} to variable '{name}' of type {var_type}",
                )

    def _assign_attr(
        self, location: Location, object: p.Expr, name: str, value_type: Type
    ):
        object_type: Type = self.type_of(object)
        member: Optional[Type] = self.types.lookup_member(object_type, name)
        if member is None:
            self.reporter.error(location, f"Unknown member '{name}' of {object_type}")
            return
        self.logger.debug(f"Member '{name}' of {object_type} has type {member}")
        if not self.is_subtype(value_type, member):
            self.reporter.error(
                location,
                f"Cannot assign {value_type} to member '{object_type}.{name}' of type {member}",
            )

    def _assign_sub(
        self,
        location: Location,
        var: p.VariableExpr,
        index: p.Expr,
        value_type: Type,
    ):
        var_type: Type = self.type_of(var)
        unfolded_type: Type = unfold_type(var_type)
        # TODO: what happens if type is an alias of a dataframe type
        match unfolded_type:
            case DataFrameType() as frame:
                new_type: Type = self.frame_mgr.assign(
                    self.reporter, location, frame, index, value_type
                )
                self.env.assign(var.name, new_type)
            case UnknownType():
                return
            case _:
                self.reporter.error(
                    location,
                    f"Cannot assign {value_type} to index {index} of {var_type}",
                )

    def visit_return_stmt(self, stmt: p.ReturnStmt) -> None:
        type: Type = self.type_of(stmt.value) if stmt.value is not None else UnitType()
        self.env.return_types.append(type)
        raise ReturnException()

    def visit_if_stmt(self, stmt: p.IfStmt) -> None:
        # Not evaluated in sub-environment because assignments in the test leak out of the if
        # For example:
        # if (m := 1 + 1) < 2:
        #     ...
        # print(m)  # <- m is still defined
        test_type: Type = self.type_of(stmt.test)

        if (
            not self.types.is_subtype(test_type, self.types.get_type("bool"))
            and test_type != UnknownType()
        ):
            self.reporter.error(
                stmt.test.location, f"If test must be a boolean, got {test_type}"
            )

        env: Environment = Environment(self.env)
        body_returned: bool = self.process_block(stmt.body, env)
        else_returned: bool = self.process_block(stmt.orelse, env)
        self.env.return_types.extend(env.return_types)
        if body_returned and else_returned:
            raise ReturnException()

    def visit_pass(self, stmt: p.Pass) -> None:
        pass

    def visit_for_stmt(self, stmt: p.ForStmt) -> None:
        item_type: Type = UnknownType()
        iterator_type: Type = self.type_of(stmt.iterator)
        if iterator_type != UnknownType():
            maybe_item_type = self._get_iterator_type(stmt.iterator, iterator_type)
            if maybe_item_type is None:
                self.reporter.error(
                    stmt.iterator.location, f"{iterator_type} is not iterable"
                )
            else:
                item_type = maybe_item_type

        self._assign(stmt.location, stmt.target, item_type)
        self.judge(stmt.target, item_type)
        env: Environment = Environment(self.env)
        body_returned: bool = self.process_block(stmt.body, env)
        if body_returned:
            raise ReturnException()

    def visit_raw_stmt(self, stmt: p.RawStmt) -> None:
        pass

    def visit_binary_expr(self, expr: p.BinaryExpr) -> Type:
        method: Optional[str] = PY_OPERATOR_METHODS.get(expr.operator.__class__)
        if method is None:
            self.logger.warning(f"Unsupported operator {expr.operator}")
            self.reporter.warning(
                expr.location, f"Unsupported operator {expr.operator}"
            )
            return UnknownType()

        return self._visit_binary_expr(expr.location, expr.left, expr.right, method)

    def visit_compare_expr(self, expr: p.CompareExpr) -> Type:
        method: Optional[str] = PY_COMPARATOR_METHODS.get(expr.operator.__class__)
        if method is None:
            self.logger.warning(f"Unsupported operator {expr.operator}")
            self.reporter.warning(
                expr.location, f"Unsupported operator {expr.operator}"
            )
            return UnknownType()

        return self._visit_binary_expr(expr.location, expr.left, expr.right, method)

    def _visit_binary_expr(
        self, location: Location, left_expr: p.Expr, right_expr: p.Expr, method: str
    ) -> Type:
        left: Type = self.type_of(left_expr)
        right: Type = self.type_of(right_expr)

        result: Optional[Type]
        try:
            result = self.call_method(location, left, method, [(right_expr, right)], {})
        except UndefinedMethodException:
            self.reporter.error(
                location,
                f"Undefined operation {method} between {left} and {right}",
            )
            return UnknownType()

        return result or UnknownType()

    def visit_unary_expr(self, expr: p.UnaryExpr) -> Type:
        method: Optional[str] = PY_UNARY_METHODS.get(expr.operator.__class__)
        if method is None:
            self.logger.warning(f"Unsupported operator {expr.operator}")
            self.reporter.warning(
                expr.location, f"Unsupported operator {expr.operator}"
            )
            return UnknownType()

        operand: Type = self.type_of(expr.right)

        result: Optional[Type]
        try:
            result = self.call_method(expr.location, operand, method, [], {})
        except UndefinedMethodException:
            self.reporter.error(
                expr.location,
                f"Undefined operation {method} for {operand}",
            )
            return UnknownType()

        return result or UnknownType()

    def visit_call_expr(self, expr: p.CallExpr) -> Type:
        match expr.callee:
            case p.VariableExpr(name="TypeVar"):
                return self.define_typevar(expr) or UnknownType()

        positional: list[TypedExpr] = [
            (arg, self.type_of(arg)) for arg in expr.arguments
        ]
        keywords: dict[str, TypedExpr] = {
            name: (arg, self.type_of(arg)) for name, arg in expr.keywords.items()
        }

        match expr.callee:
            case p.GetExpr(object=obj, name=method):
                obj_type: Type = self.type_of(obj)
                unfolded: Type = unfold_type(obj_type)
                if isinstance(unfolded, DataFrameType):
                    return self.frame_mgr.call(
                        method,
                        expr.location,
                        unfolded,
                        positional,
                        keywords,
                    )

        callee: Type = self.type_of(expr.callee)
        result: CallResult = self.dispatcher.get_result(
            location=expr.location,
            callee=callee,
            positional=positional,
            keywords=keywords,
        )
        return result.result

    def visit_get_expr(self, expr: p.GetExpr) -> Type:
        object: Type = self.type_of(expr.object)
        member: Optional[Type] = self.types.lookup_member(object, expr.name)
        if member is None:
            self.reporter.warning(
                expr.location, f"Unknown member '{expr.name}' of {object}"
            )
            return UnknownType()
        self.logger.debug(f"Member '{expr.name}' of {object} has type {member}")
        return member

    def visit_literal_expr(self, expr: p.LiteralExpr) -> Type:
        match expr.value:
            case bool():  # Must be before int
                return self.types.get_type("bool")
            case int():
                return self.types.get_type("int")
            case float():
                return self.types.get_type("float")
            case str():
                return self.types.get_type("str")
            case None:
                return self.types.get_type("None")
            case _:
                self.reporter.warning(expr.location, f"Unknown literal {expr}")
                return UnknownType()

    def visit_variable_expr(self, expr: p.VariableExpr) -> Type:
        type: Optional[Type] = self.look_up_variable(expr.name, expr)
        if type is None:
            self.logger.debug(f"Unknown variable {expr.name} in {self.env.flat_dict()}")
            self.reporter.warning(expr.location, "Unknown variable")
        return type or UnknownType()

    def visit_logical_expr(self, expr: p.LogicalExpr) -> Type:
        left: Type = self.type_of(expr.left)
        right: Type = self.type_of(expr.right)

        if self.is_subtype(left, right):
            return right
        if self.is_subtype(right, left):
            return left

        self.reporter.error(
            expr.location,
            f"Incompatible operand types, {left=} and {right=}",
        )
        return UnknownType()

    def visit_cast_expr(self, expr: p.CastExpr) -> Type:
        subject_type: Type = self.type_of(expr.expr)
        target_type: Type = self.resolve_type_expr(expr.type)
        is_lit, lit_value = self._get_literal(expr.expr)
        if is_lit:
            evaluated: bool = self._evaluate_cast_statically(
                expr, subject_type, target_type, lit_value
            )
            if evaluated:
                self.evaluated_casts.append(expr)
        return target_type

    def visit_ternary_expr(self, expr: p.TernaryExpr) -> Type:
        test_type: Type = self.type_of(expr.test)

        # TODO Allow subtypes or any type
        if (
            not self.is_subtype(test_type, self.types.get_type("bool"))
            and test_type != UnknownType()
        ):
            self.reporter.error(
                expr.test.location, f"If test must be a boolean, got {test_type}"
            )

        true_type: Type = self.type_of(expr.if_true)
        false_type: Type = self.type_of(expr.if_false)
        if self.is_subtype(true_type, false_type):
            return false_type
        if self.is_subtype(false_type, true_type):
            return true_type

        self.reporter.error(
            expr.location,
            f"Incompatible types in ternary if branches: true={true_type} and false={false_type}",
        )
        return UnknownType()

    def visit_list_expr(self, expr: p.ListExpr) -> Type:
        list_type: Type = self.types.get_type("list")
        item_types: list[Type] = [self.type_of(item) for item in expr.items]
        item_types = self.types.reduce_types(item_types)

        if len(item_types) == 0:
            return list_type

        if len(item_types) == 1:
            item_type: Type = item_types[0]
            return self.types.apply_generic(list_type, [item_type])
        self.reporter.warning(
            expr.location,
            f"Heterogeneous list items: [{', '.join(map(str, item_types))}]",
        )
        return self.types.apply_generic(list_type, [UnknownType()])

    def visit_dict_expr(self, expr: p.DictExpr) -> Type:
        dict_type: Type = self.types.get_type("dict")

        key_types: list[Type] = []
        value_types: list[Type] = []
        for key, value in zip(expr.keys, expr.values):
            if key is None:
                self.reporter.warning(
                    value.location, "Dictionary unpacking not supported"
                )
                continue
            key_types.append(self.type_of(key))
            value_types.append(self.type_of(value))

        key_types = self.types.reduce_types(key_types)
        value_types = self.types.reduce_types(value_types)

        if len(key_types) == 0 or len(value_types) == 0:
            return dict_type

        key_type: Type = UnknownType()
        value_type: Type = UnknownType()

        if len(key_types) == 1:
            key_type = key_types[0]
        else:
            self.reporter.warning(
                expr.location,
                f"Heterogeneous dict keys: [{', '.join(map(str, key_types))}]",
            )

        if len(value_types) == 1:
            value_type = value_types[0]
        else:
            self.reporter.warning(
                expr.location,
                f"Heterogeneous dict values: [{', '.join(map(str, value_types))}]",
            )
        return self.types.apply_generic(dict_type, [key_type, value_type])

    def visit_subscript_expr(self, expr: p.SubscriptExpr) -> Type:
        object: Type = self.type_of(expr.object)
        unfolded: Type = unfold_type(object)
        match unfolded:
            case TupleType():
                return self._visit_tuple_subscript(unfolded, expr)
            case DataFrameType():
                return self._visit_frame_subscript(unfolded, expr)

        operation: Optional[Type] = self.types.lookup_member(object, "__getitem__")
        if operation is None:
            self.reporter.error(
                expr.location,
                f"Undefined method __getitem__ on {object}",
            )
            return UnknownType()

        index: Type = self.type_of(expr.index)
        result: CallResult = self.dispatcher.get_result(
            location=expr.location,
            callee=operation,
            positional=[(expr.index, index)],
            keywords={},
        )
        return result.result

    def visit_slice_expr(self, expr: p.SliceExpr) -> Type:
        return self.types.get_type("slice")

    def visit_tuple_expr(self, expr: p.TupleExpr) -> Type:
        return TupleType(
            items=tuple(self.type_of(item) for item in expr.items),
        )

    def visit_raw_expr(self, expr: p.RawExpr) -> Type:
        return UnknownType()

    def visit_base_type(self, node: p.BaseType) -> Type:
        base: Type
        try:
            base = self.types.get_type(node.base)
        except NameError:
            self.reporter.warning(node.location, f"Unknown type '{node.base}'")
            return UnknownType()

        if len(node.args) != 0:
            args: list[Type] = [self.resolve_type_expr(arg) for arg in node.args]
            return self.types.apply_generic(base, args)
        return base

    def visit_constraint_type(self, node: p.ConstraintType) -> Type:
        self.reporter.warning(node.location, "ConstraintType not yet supported")
        return UnknownType()

    def visit_frame_column(self, node: p.FrameColumn) -> ColumnType:
        return ColumnType(
            type=(
                self.resolve_type_expr(node.type)
                if node.type is not None
                else UnknownType()
            )
        )

    def visit_frame_type(self, node: p.FrameType) -> Type:
        return DataFrameType(
            columns=[
                DataFrameType.Column(
                    index=i,
                    name=column.name,
                    type=self.visit_frame_column(column),
                )
                for i, column in enumerate(node.columns)
            ]
        )

    def _get_iterator_type(self, expr: p.Expr, type: Type) -> Optional[Type]:
        # TODO: lookup __iter__
        getitem: Optional[Type] = self.types.lookup_member(type, "__getitem__")
        if getitem is None:
            return None

        index: p.Expr = p.LiteralExpr(location=expr.location, value=0)
        index_type: Type = self.compute_type(index)
        result: CallResult = self.dispatcher.get_result(
            location=expr.location,
            callee=getitem,
            positional=[(index, index_type)],
            keywords={},
            report_errors=False,
        )
        if not result.is_valid:
            return None
        return result.result

    def define_typevar(self, call: p.CallExpr) -> Optional[TypeVar]:
        def is_kw_true(name: str) -> bool:
            match call.keywords.get(name):
                case p.LiteralExpr(value=True):
                    return True
                case _:
                    return False

        match call:
            case p.CallExpr(
                arguments=[p.LiteralExpr(value=str() as name)],
            ):
                bound: Optional[Type] = None
                variance: Variance = Variance.INVARIANT
                if "bound" in call.keywords:
                    bound_type: p.MidasType = self._parse_type_from_expr(
                        call.keywords["bound"]
                    )
                    bound = self.resolve_type_expr(bound_type)

                if is_kw_true("covariant"):
                    variance = Variance.COVARIANT

                if is_kw_true("contravariant"):
                    if variance == Variance.COVARIANT:
                        self.reporter.warning(
                            call.keywords["contravariant"].location,
                            "TypeVar cannot be covariant and contravariant at the same time. Marked as invariant",
                        )
                        variance = Variance.INVARIANT
                    else:
                        variance = Variance.CONTRAVARIANT
                var: TypeVar = TypeVar(name=name, bound=bound, variance=variance)
                self.types.define_type(name, var)
                return var

            case _:
                self.reporter.warning(
                    call.location, "Invalid usage of 'TypeVar', skipping"
                )
                return None

    def _parse_type_from_expr(self, expr: p.Expr) -> p.MidasType:
        location: Location = expr.location
        parser = PythonParser()
        match expr:
            case p.LiteralExpr(value=str() as value):
                node: ast.Expression = ast.parse(value, mode="eval")
                return parser._parse_type(node.body)
            case p.VariableExpr(name=name):
                return p.BaseType(location=location, base=name, args=())
            case _:
                raise NotImplementedError

    def _get_literal(self, expr: p.Expr) -> tuple[bool, Any]:
        match expr:
            case p.LiteralExpr(value=value):
                return True, value

            case p.ListExpr(items=items):
                values: list[Any] = []
                for item in items:
                    is_lit, value = self._get_literal(item)
                    if not is_lit:
                        return False, None
                    values.append(value)
                return True, values

            case p.DictExpr(keys=keys, values=values):
                pairs: list[tuple[Any, Any]] = []
                for key, value in zip(keys, values):
                    key_val = None
                    if key is not None:
                        is_lit, key_val = self._get_literal(key)
                        if not is_lit:
                            return False, None

                    is_lit, value_val = self._get_literal(value)
                    if not is_lit:
                        return False, None

                    if key is None:
                        # TODO: check that value is always a dict
                        assert isinstance(value_val, dict)
                        pairs.extend(value_val.items())
                    else:
                        pairs.append((key_val, value_val))
                return True, dict(pairs)

            case p.UnaryExpr(operator=operator, right=operand):
                is_lit, operand_val = self._get_literal(operand)
                if not is_lit:
                    return False, None
                match operator:
                    case ast.UAdd():
                        return True, operand_val
                    case ast.USub():
                        return True, -operand_val
                    case ast.Invert():
                        return True, ~operand_val
                    case ast.Not():
                        return True, not operand_val
                    case _:  # Should never be reached
                        return False, None

            case _:
                return False, None

    def _evaluate_cast_statically(
        self, expr: p.CastExpr, subject_type: Type, target_type: Type, lit_value: Any
    ) -> bool:
        match target_type:
            case DerivedType(type=base):
                return self._evaluate_cast_statically(
                    expr, subject_type, base, lit_value
                )

            case AppliedType(name="list", args=[item_type]) if isinstance(
                lit_value, list
            ):
                match subject_type:
                    case AppliedType(name="list", args=[lit_item_type]):
                        evaluated: bool = True
                        for item in lit_value:
                            if not self._evaluate_cast_statically(
                                expr, lit_item_type, item_type, item
                            ):
                                evaluated = False
                        return evaluated
                    case _:
                        return False

            case AppliedType(name="dict", args=[key_type, value_type]) if isinstance(
                lit_value, dict
            ):
                match subject_type:
                    case AppliedType(name="dict", args=[lit_key_type, lit_value_type]):
                        evaluated: bool = True
                        for key, value in lit_value.items():
                            if not self._evaluate_cast_statically(
                                expr, lit_key_type, key_type, key
                            ):
                                evaluated = False
                            if not self._evaluate_cast_statically(
                                expr, lit_value_type, value_type, value
                            ):
                                evaluated = False
                        return evaluated
                    case _:
                        return False

            case AppliedType(body=body):
                return self._evaluate_cast_statically(
                    expr, subject_type, body, lit_value
                )

            case ConstraintType(type=base, constraint=constraint):
                evaluated: bool = True
                if not self._evaluate_cast_statically(
                    expr, subject_type, base, lit_value
                ):
                    evaluated = False

                evaluator = Evaluator(self.types)
                evaluator.set_value("_", lit_value)
                res = evaluator.evaluate(constraint)
                if not res:
                    printer = MidasPrinter()
                    constraint_str: str = printer.print(constraint)
                    self.reporter.error(
                        expr.location,
                        f"Value {lit_value!r} does not fit constraint '{constraint_str}'",
                    )
                    evaluated = False
                return evaluated

            case BaseType():
                # TODO: do we want to allow cast(float, int)? would require runtime conversion
                if not self.types.is_subtype(
                    subject_type, target_type
                ) or not self.types.is_subtype(target_type, subject_type):
                    self.reporter.error(
                        expr.location,
                        f"Value {lit_value!r} of type {subject_type} cannot be cast as {target_type}",
                    )
                    return False
                return True

            case DataFrameType() | ColumnType():
                self.reporter.error(
                    expr.location, f"Cannot cast {lit_value!r} to {target_type}"
                )
                return False

            case _:
                self.reporter.info(
                    expr.location, f"Cannot evaluate cast to {target_type} statically"
                )
                return False

    def _visit_tuple_subscript(self, tup: TupleType, expr: p.SubscriptExpr) -> Type:
        match expr.index:
            case p.LiteralExpr(value=int() as index):
                if index < 0 or index >= len(tup.items):
                    self.reporter.error(
                        expr.location, f"Index {index} out of range for tuple {tup}"
                    )
                    return UnknownType()
                return tup.items[index]
            case _:
                self.reporter.error(
                    expr.location, f"Invalid index type {expr.index} on {tup}"
                )
                return UnknownType()

    def _visit_frame_subscript(
        self, frame: DataFrameType, expr: p.SubscriptExpr
    ) -> Type:
        return self.frame_mgr.get(self.reporter, expr.location, frame, expr.index)
