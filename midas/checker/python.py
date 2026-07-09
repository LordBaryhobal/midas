import ast
import logging
from typing import Any, Optional

import midas.ast.python as p
from midas.ast.location import Location
from midas.ast.printer import MidasPrinter
from midas.checker.dispatcher import CallDispatcher, CallResult
from midas.checker.environment import Environment
from midas.checker.evaluator import Evaluator
from midas.checker.frames.column_manager import ColumnManager
from midas.checker.frames.frame_manager import FrameManager
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
    ColumnGroupBy,
    ColumnType,
    ConstraintType,
    DataFrameType,
    DerivedType,
    FrameGroupBy,
    Function,
    GenericType,
    ParamSpec,
    TopType,
    TupleType,
    Type,
    TypeVar,
    UnitType,
    UnknownType,
    Variance,
    unfold_type,
)
from midas.generator.collector import AssertionCollector
from midas.parser.python import PythonParser
from midas.utils import TypedAST

TypedExpr = tuple[p.Expr, Type]


class ReturnException(Exception):
    pass


class UndefinedMethodException(Exception):
    pass


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
        self.column_mgr: ColumnManager = ColumnManager(self)
        self.global_env: Environment = Preamble(self.types)
        self.env: Environment = self.global_env
        self.locals: dict[p.Expr, int] = {}
        self.judgements: list[tuple[p.Expr, Type]] = []
        self.evaluated_casts: list[p.CastExpr] = []
        self.dispatcher: CallDispatcher[p.Expr] = CallDispatcher[p.Expr](
            self.types, self.reporter
        )
        self.assertions: AssertionCollector = AssertionCollector()

    def set_reporter(self, reporter: FileReporter):
        """Set the file reporter to use for diagnostics

        Args:
            reporter (FileReporter): the file reporter
        """
        self.reporter = reporter
        self.dispatcher.set_reporter(self.reporter)

    def process(self, source: str, path: Optional[str]) -> TypedAST:
        """Process some Python source code

        Args:
            source (str): the Python source code
            path (Optional[str]): the path of the source file, if known

        Returns:
            TypedAST: all generated typechecking information
        """
        reporter: FileReporter = self.reporter.for_file(path)
        self.set_reporter(reporter)

        tree: ast.Module = ast.parse(source, filename=path or "<unknown>")
        parser = PythonParser()
        stmts: list[p.Stmt] = parser.parse_module(tree)
        resolver = Resolver(reporter)
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
            assertions=self.assertions,
        )

    def judge(self, expr: p.Expr, type: Type):
        """Record a typing judgement for the given expression

        Args:
            expr (p.Expr): the judged expression
            type (Type): the type of the expression
        """
        self.judgements.append((expr, type))

    def compute_type(self, expr: p.Expr) -> Type:
        """Evaluate the type of the given expression

        Args:
            expr (p.Expr): the expression to type

        Returns:
            Type: the type of the given expression
        """
        return expr.accept(self)

    def type_of(self, expr: p.Expr) -> Type:
        """Evaluate the type of the given expression and record the judgement

        Args:
            expr (p.Expr): the expression to evaluate

        Returns:
            Type: the type of the given expression
        """
        type: Type = self.compute_type(expr)
        self.judge(expr, type)
        return type

    def resolve_type_expr(self, expr: p.MidasType) -> Type:
        """Resolve the type of a type expression (annotation)

        Args:
            expr (p.MidasType): the type expression

        Returns:
            Type: the resolved type
        """
        return expr.accept(self)

    def process_stmt(self, stmt: p.Stmt) -> None:
        """Type check the given statement

        Args:
            stmt (p.Stmt): the statement to type-check
        """
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
        call_expr: p.Expr,
        obj: TypedExpr,
        method_name: str,
        positional: list[TypedExpr],
        keywords: dict[str, TypedExpr],
    ) -> Type:
        """Evaluate a method call on an object

        Calls to dataframes and columns types are delegated to the appropriate manager

        Args:
            location (Location): the location of the call
            call_expr (p.Expr): the call expression
            obj (TypedExpr): the object on which the method is called
            method_name (str): the method name
            positional (list[TypedExpr]): the list of positional arguments
            keywords (dict[str, TypedExpr]): the map of keyword arguments

        Raises:
            UndefinedMethodException: if the method is not defined

        Returns:
            Type: the return type of the call
        """
        unfolded: Type = unfold_type(obj[1])
        match unfolded:
            case TopType() | UnknownType():
                return UnknownType()

            case DataFrameType():
                return self.frame_mgr.call(
                    method=method_name,
                    location=location,
                    call_expr=call_expr,
                    frame=unfolded,
                    frame_expr=obj[0],
                    positional=positional,
                    keywords=keywords,
                )

            case FrameGroupBy():
                return self.frame_mgr.groupby_call(
                    method=method_name,
                    location=location,
                    call_expr=call_expr,
                    groupby=unfolded,
                    groupby_expr=obj[0],
                    positional=positional,
                    keywords=keywords,
                )

            case ColumnType():
                return self.column_mgr.call(
                    method=method_name,
                    location=location,
                    call_expr=call_expr,
                    column=unfolded,
                    column_expr=obj[0],
                    positional=positional,
                    keywords=keywords,
                )

            case ColumnGroupBy():
                return self.column_mgr.groupby_call(
                    method=method_name,
                    location=location,
                    call_expr=call_expr,
                    groupby=unfolded,
                    groupby_expr=obj[0],
                    positional=positional,
                    keywords=keywords,
                )

        method: Optional[Type] = self.types.lookup_member(obj[1], method_name)
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
        """Check whether `type1` is a subtype of `type2`

        Args:
            type1 (Type): the potential "subtype"
            type2 (Type): the potential "supertype"

        Returns:
            bool: whether `type1` is a subtype of `type2`
        """
        return self.types.is_subtype(type1, type2)

    def visit_expression_stmt(self, stmt: p.ExpressionStmt) -> None:
        self.type_of(stmt.expr)

    def visit_function(self, stmt: p.Function) -> None:
        env: Environment = Environment(self.env)
        pos: list[Function.Parameter] = []
        mixed: list[Function.Parameter] = []
        kw: list[Function.Parameter] = []

        def eval_param_type(param: p.Function.Parameter) -> Type:
            default_type: Optional[Type] = None
            if param.default is not None:
                default_type = self.type_of(param.default)

            if param.type is not None:
                param_type: Type = self.resolve_type_expr(param.type)
                if default_type is not None:
                    if not self.types.is_subtype(default_type, param_type):
                        self.reporter.error(
                            param.location or stmt.location,
                            f"Cannot use default value of type {default_type} for parameter of type {param_type}",
                        )
                return param_type

            if default_type is not None:
                return default_type

            return UnknownType()

        position: int = 0
        for param in stmt.params.pos:
            pos.append(
                Function.Parameter(
                    pos=position,
                    name=param.name,
                    type=eval_param_type(param),
                    required=param.default is None,
                )
            )
            position += 1
        for param in stmt.params.mixed:
            mixed.append(
                Function.Parameter(
                    pos=position,
                    name=param.name,
                    type=eval_param_type(param),
                    required=param.default is None,
                )
            )
            position += 1
        for param in stmt.params.kw:
            kw.append(
                Function.Parameter(
                    pos=position,  # not relevant
                    name=param.name,
                    type=eval_param_type(param),
                    required=param.default is None,
                )
            )
            position += 1

        param_spec: ParamSpec = ParamSpec(
            pos=pos,
            mixed=mixed,
            kw=kw,
        )
        all_params: list[Function.Parameter] = pos + mixed + kw
        for param in all_params:
            env.define(param.name, param.type)

        returns_hint: Optional[Type] = None
        if stmt.returns is not None:
            returns_hint = self.resolve_type_expr(stmt.returns)
            # Early define to handle simple fully-typed recursion
            inside_function: Function = Function(
                params=param_spec,
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
            params=param_spec,
            returns=returns,
        )
        generic_params: list[TypeVar] = []
        all_types: list[Type] = [param.type for param in all_params] + [returns]
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
        type: Type = self.resolve_type_expr(stmt.type)
        self.env.define(stmt.name, type)

    def visit_assign_stmt(self, stmt: p.AssignStmt) -> None:
        value_type: Type = self.type_of(stmt.value)
        for target in stmt.targets:
            self._assign(stmt.location, target, value_type)

    def _assign(self, location: Location, target: p.Expr, value_type: Type):
        """Handle an assignment to the given target

        Delegate to the appropriate method according to the target type

        Args:
            location (Location): the location of the assignment
            target (p.Expr): the assignment's target
            value_type (Type): the value to be assigned
        """
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
                self.logger.warning(f"Unsupported assignment to {target}")
                self.reporter.warning(
                    target.location, f"Unsupported assignment to {target}"
                )

    def _assign_var(self, location: Location, target: p.VariableExpr, value_type: Type):
        """Type check assignment to the given target

        Args:
            location (Location): the location of the assignment
            target (p.VariableExpr): the assignment's target
            value_type (Type): the value to be assigned
        """
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
        """Type check assignment to the given attribute target

        Args:
            location (Location): the location of the assignment
            object (p.Expr): the target attribute's owner object
            name (str): the target attribute's name
            value_type (Type): the value to be assigned
        """
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
        """Type check assignment to the given subscript target

        Args:
            location (Location): the location of the assignment
            var (p.VariableExpr): the target subscript's owner. We only allow
                a variable expression here because we might modify its type (for
                example when assigning a column to a dataframe) and reference
                types are not implemented
            index (p.Expr): the target subscript's index expression
            value_type (Type): the value to be assigned
        """
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
        outer_env: Environment = self.env
        inner_env: Environment = Environment(self.env)
        self.env = inner_env

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
        body_returned: bool = self.process_block(stmt.body, inner_env)

        self.env = outer_env

        if body_returned:
            raise ReturnException()

    def visit_import_stmt(self, stmt: p.ImportStmt) -> None:
        self._visit_imports(stmt.location, stmt.imports)

    def visit_from_import_stmt(self, stmt: p.FromImportStmt) -> None:
        self._visit_imports(stmt.location, stmt.imports)

    def _visit_imports(self, location: Location, imports: list[p.ImportAlias]) -> None:
        for import_ in imports:
            self._assign_var(
                location,
                p.VariableExpr(
                    name=import_.imported_name,
                    location=import_.location,
                ),
                UnknownType(),
            )

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

        left: Type = self.type_of(expr.left)
        right: Type = self.type_of(expr.right)
        return self.result_of_binary_op(
            expr.location,
            expr,
            (expr.left, left),
            (expr.right, right),
            method,
        )

    def visit_compare_expr(self, expr: p.CompareExpr) -> Type:
        method: Optional[str] = PY_COMPARATOR_METHODS.get(expr.operator.__class__)
        if method is None:
            self.logger.warning(f"Unsupported operator {expr.operator}")
            self.reporter.warning(
                expr.location, f"Unsupported operator {expr.operator}"
            )
            return UnknownType()

        left: Type = self.type_of(expr.left)
        right: Type = self.type_of(expr.right)
        return self.result_of_binary_op(
            expr.location,
            expr,
            (expr.left, left),
            (expr.right, right),
            method,
        )

    def result_of_binary_op(
        self,
        location: Location,
        expr: p.Expr,
        left: TypedExpr,
        right: TypedExpr,
        method: str,
    ) -> Type:
        """Compute the result type of a binary operation method call

        This method is called for dunder methods called by binary operators

        Args:
            location (Location): the location of the operation
            expr (p.Expr): the expression which triggered this resolution
            left (TypedExpr): the left operand
            right (TypedExpr): the right operand
            method (str): the method name

        Returns:
            Type: the result type
        """
        try:
            return self.call_method(
                location=location,
                call_expr=expr,
                obj=left,
                method_name=method,
                positional=[right],
                keywords={},
            )
        except UndefinedMethodException:
            self.reporter.error(
                location,
                f"Undefined operation {method} between {left[1]} and {right[1]}",
            )
            return UnknownType()

    def visit_unary_expr(self, expr: p.UnaryExpr) -> Type:
        # Special case because there is no __not__ dunder method
        match expr.operator:
            case ast.Not():
                return self.types.get_type("bool")

        method: Optional[str] = PY_UNARY_METHODS.get(expr.operator.__class__)
        if method is None:
            self.logger.warning(f"Unsupported operator {expr.operator}")
            self.reporter.warning(
                expr.location, f"Unsupported operator {expr.operator}"
            )
            return UnknownType()

        operand: Type = self.type_of(expr.right)

        try:
            return self.call_method(
                location=expr.location,
                call_expr=expr,
                obj=(expr.right, operand),
                method_name=method,
                positional=[],
                keywords={},
            )
        except UndefinedMethodException:
            self.reporter.error(
                expr.location,
                f"Undefined operation {method} for {operand}",
            )
            return UnknownType()

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
                return self.call_method(
                    location=expr.location,
                    call_expr=expr,
                    obj=(obj, obj_type),
                    method_name=method,
                    positional=positional,
                    keywords=keywords,
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
            match object:
                case DataFrameType():
                    member = self.frame_mgr.get_attribute(object, expr.name)
                case ColumnType():
                    member = self.column_mgr.get_attribute(object, expr.name)

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

        # Strict: test must be a subtype of bool, or UnknownType
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
            case FrameGroupBy():
                return self._visit_frame_groupby_subscript(unfolded, expr)
            case ColumnType():
                return self._visit_column_subscript(unfolded, expr)

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
        if node.base == "Column":
            if len(node.args) != 1:
                self.reporter.error(
                    node.location,
                    f"Column requires 1 type argument, {len(node.args)} provided",
                )
                return ColumnType(type=UnknownType())
            return ColumnType(type=self.resolve_type_expr(node.args[0]))

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
        """Get the item type of an iterator type

        Args:
            expr (p.Expr): the iterator expression
            type (Type): the iterator type

        Returns:
            Optional[Type]: the item type, or `None` if it cannot be determined
        """
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
        """Define a type variable from a call to `typing.TypeVar`

        Args:
            call (p.CallExpr): the call to `typing.TypeVar`

        Returns:
            Optional[TypeVar]: the define type variable, or `None` if the call
                is invalid
        """

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
        """Parse a type expression from a raw expression

        This is useful for expressions inside a `TypeVar`'s `bound` parameter

        Args:
            expr (p.Expr): the expression to parse

        Raises:
            NotImplementedError: if the expression is not supported

        Returns:
            p.MidasType: the parsed type node
        """
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
        """Get the literal value of a literal-like expression

        Args:
            expr (p.Expr): the expression

        Returns:
            tuple[bool, Any]: a tuple containing a boolean indicating whether
                the given expression is literal-like, and the literal value (or
                `None` if the first value is `False`)
        """
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
                        # If literal value is not a dict, invalid Python -> abort
                        if not isinstance(value_val, dict):
                            return False, None
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
        """Evaluate the given cast expression statically

        Args:
            expr (p.CastExpr): the cast expression
            subject_type (Type): the subject type being casted
            target_type (Type): the target type to which the expression is casted
            lit_value (Any): the literal value of the expression

        Returns:
            bool: whether the cast expression could be evaluated successfully
        """
        match target_type:
            case TopType():
                return True

            case UnitType():
                if lit_value is not None:
                    self.reporter.error(
                        expr.location, f"Value {lit_value!r} is not None"
                    )
                    return False
                return True

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
                printer = MidasPrinter()
                constraint_str: str = printer.print(constraint)
                res: Any
                try:
                    res = evaluator.evaluate(constraint)
                except Exception as e:
                    self.reporter.error(
                        expr.location,
                        f"An error occurred while checking constraint '{constraint_str}' on the value {lit_value!r}: {e}",
                    )
                    return False

                if not res:
                    self.reporter.error(
                        expr.location,
                        f"Value {lit_value!r} does not fit constraint '{constraint_str}'",
                    )
                    evaluated = False
                return evaluated

            case BaseType():
                # TODO: do we want to allow cast(float, int)? would require runtime conversion
                if not self.types.are_equivalent(subject_type, target_type):
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

    def _visit_frame_groupby_subscript(
        self, groupby: FrameGroupBy, expr: p.SubscriptExpr
    ) -> Type:
        return self.frame_mgr.groupby_get(
            self.reporter, expr.location, groupby, expr.index
        )

    def _visit_column_subscript(
        self, column: ColumnType, expr: p.SubscriptExpr
    ) -> Type:
        index_type: Type = self.type_of(expr.index)
        return self.column_mgr.get(
            self.reporter,
            expr.location,
            column,
            (expr.index, index_type),
        )
