from typing import Optional

import midas.ast.midas as m
from midas.checker.builtins import BUILTIN_SUBTYPES
from midas.checker.types import (
    AliasType,
    BaseType,
    ComplexType,
    Function,
    GenericType,
    Operation,
    Type,
    TypeVar,
    UnknownType,
    substitute_typevars,
)
from midas.resolver.builtin import define_builtins


class MidasResolver(m.Stmt.Visitor[None], m.Expr.Visitor[None], m.Type.Visitor[Type]):
    """A resolver which evaluates Midas type definitions and build a registry"""

    def __init__(self) -> None:
        self._types: dict[str, Type] = {}
        self._operations: dict[Operation.CallSignature, Type] = {}

        self._local_variables: dict[str, TypeVar] = {}

        define_builtins(self)

    def get_type(self, name: str) -> Type:
        """Get a type from its name

        Args:
            name (str): the name of the type

        Raises:
            NameError: if the type is not defined

        Returns:
            Type: the type
        """
        if name in self._local_variables:
            return self._local_variables[name]
        if name in self._types:
            return self._types[name]
        raise NameError(f"Undefined type {name}")

    def get_operation_result(
        self, left: Type, operator: str, right: Type
    ) -> Optional[Type]:
        """Get the resulting type of an operation

        Args:
            left (Type): the type of the left operand
            operator (str): the operation name
            right (Type): the type of the right operand

        Returns:
            Optional[Type]: the result type, or None if no matching operation was found
        """
        signature: Operation.CallSignature = Operation.CallSignature(
            left=left,
            method=operator,
            right=right,
        )
        result: Optional[Type] = self._operations.get(signature)
        return result

    def get_operations_by_name(self, name: str) -> list[Operation]:
        operations: list[Operation] = []
        for signature, result in self._operations.items():
            if signature.method == name:
                operations.append(
                    Operation(
                        signature=signature,
                        result=result,
                    )
                )
        return operations

    def define_type(self, name: str, type: Type) -> Type:
        """Define a type in the registry

        Args:
            name (str): the name of the type
            type (Type): the type to define

        Raises:
            ValueError: if a type is already defined with that name

        Returns:
            Type: the defined type
        """
        if name in self._types:
            raise ValueError(f"Type {name} already defined")
        self._types[name] = type
        return type

    def define_operation(self, left: Type, operator: str, right: Type, result: Type):
        """Define an operation in the registry

        Args:
            left (Type): the type of the left operand
            operator (str): the operation name
            right (Type): the type of the right operand
            result (Type): the result type

        Raises:
            ValueError: if an operation is already defined with these operands and name
        """
        signature: Operation.CallSignature = Operation.CallSignature(
            left=left,
            method=operator,
            right=right,
        )
        if signature in self._operations:
            raise ValueError(
                f"Operation {operator} already defined between {left} and {right}"
            )
        self._operations[signature] = result

    def resolve(self, stmts: list[m.Stmt]):
        """Process a sequence of statements

        Args:
            stmts (list[m.Stmt]): the statements
        """
        for stmt in stmts:
            stmt.accept(self)

    def visit_type_stmt(self, stmt: m.TypeStmt) -> None:
        params: list[TypeVar] = []
        for param in stmt.params:
            name: str = param.name.lexeme
            bound: Optional[Type] = None
            if param.bound is not None:
                bound = param.bound.accept(self)
            var = TypeVar(name=name, bound=bound)
            self._local_variables[name] = var
            params.append(var)
        type: Type = stmt.type.accept(self)
        if len(params) != 0:
            type = GenericType(params=params, body=type)
        name: str = stmt.name.lexeme
        self.define_type(name, AliasType(name=name, type=type))
        self._local_variables.clear()

    def visit_property_stmt(self, stmt: m.PropertyStmt) -> None: ...

    def visit_extend_stmt(self, stmt: m.ExtendStmt) -> None:
        base: Type = stmt.type.accept(self)
        for op in stmt.operations:
            right: Type = op.operand.accept(self)
            result: Type = op.result.accept(self)
            self.define_operation(
                left=base,
                operator=op.name.lexeme,
                right=right,
                result=result,
            )

    def visit_op_stmt(self, stmt: m.OpStmt) -> None: ...

    def visit_predicate_stmt(self, stmt: m.PredicateStmt) -> None: ...

    def visit_logical_expr(self, expr: m.LogicalExpr) -> None: ...

    def visit_binary_expr(self, expr: m.BinaryExpr) -> None: ...

    def visit_unary_expr(self, expr: m.UnaryExpr) -> None: ...

    def visit_get_expr(self, expr: m.GetExpr) -> None: ...

    def visit_variable_expr(self, expr: m.VariableExpr) -> None: ...

    def visit_grouping_expr(self, expr: m.GroupingExpr) -> None:
        return expr.expr.accept(self)

    def visit_literal_expr(self, expr: m.LiteralExpr) -> None: ...

    def visit_wildcard_expr(self, expr: m.WildcardExpr) -> None: ...

    def visit_named_type(self, type: m.NamedType) -> Type:
        return self.get_type(type.name.lexeme)

    def visit_generic_type(self, type: m.GenericType) -> Type:
        type_: Type = type.type.accept(self)
        params: list[Type] = [param.accept(self) for param in type.params]
        return self.apply_generic(type_, params)

    def apply_generic(self, type: Type, params: list[Type]) -> Type:
        match type:
            case AliasType(name=name, type=base):
                return AliasType(name=name, type=self.apply_generic(base, params))

            case GenericType(params=type_vars, body=body):
                n_params: int = len(params)
                n_type_vars: int = len(type_vars)
                if n_params < n_type_vars:
                    raise ValueError(
                        f"Missing type parameters, expected {n_type_vars} but only {n_params} provided"
                    )
                if n_params > n_type_vars:
                    raise ValueError(
                        f"Too many type parameters, expected {n_type_vars} but {n_params} provided"
                    )
                substitutions: dict[str, Type] = {}
                for param, type_var in zip(params, type_vars):
                    if type_var.bound is not None and not self.is_subtype(
                        param, type_var.bound
                    ):
                        raise ValueError(
                            f"Type parameter {param} is not a subtype of {type_var.bound}"
                        )
                    substitutions[type_var.name] = param
                return substitute_typevars(body, substitutions)
            case _:
                raise ValueError(f"{type} is not a generic type")

    def visit_constraint_type(self, type: m.ConstraintType) -> Type:
        type_: Type = type.type.accept(self)
        type.constraint.accept(self)
        # TODO
        return UnknownType()

    def visit_complex_type(self, type: m.ComplexType) -> Type:
        return ComplexType(
            properties={
                prop.name.lexeme: prop.type.accept(self) for prop in type.properties
            }
        )

    def is_subtype(self, type1: Type, type2: Type) -> bool:
        """Check whether `type1` is a subtype of `type2`

        For more details on the rules checked here, see TAPL Chap. 15-16-17

        Args:
            type1 (Type): the potential subtype
            type2 (Type): the potential supertype

        Returns:
            bool: whether `type1` is a subtype of `type2`
        """

        if type1 == type2:
            return True

        match (type1, type2):
            case (AliasType(type=base1), _):
                return self.is_subtype(base1, type2)

            case (BaseType(name=name1), BaseType(name=name2)):
                return name1 in BUILTIN_SUBTYPES.get(name2, set())

            case (ComplexType(properties=props1), ComplexType(properties=props2)):
                for k, t in props2.items():
                    if k not in props1:
                        return False
                    if not self.is_subtype(props1[k], t):
                        return False
                return True

            case (Function(), Function()):
                return self.is_func_subtype(type1, type2)

        return False

    # TODO: verify the logic in here
    def is_func_subtype(self, func1: Function, func2: Function) -> bool:
        """Check whether a function is a subtype of another

        Args:
            func1 (Function): the potential function subtype
            func2 (Function): the potential function supertype

        Returns:
            bool: whether `func1` is a subtype of `func2`
        """
        if not self.is_subtype(func1.returns, func2.returns):
            return False

        pos1: list[Function.Argument] = func1.pos_args
        mixed1: list[Function.Argument] = func1.args
        kw1: dict[str, Function.Argument] = {a.name: a for a in func1.kw_args}
        pos2: list[Function.Argument] = func2.pos_args
        mixed2: list[Function.Argument] = func2.args
        kw2: dict[str, Function.Argument] = {a.name: a for a in func2.kw_args}

        mixed_by_pos: dict[int, Function.Argument] = {arg.pos: arg for arg in mixed2}
        mixed_by_name: dict[str, Function.Argument] = {arg.name: arg for arg in mixed2}

        def is_arg_subtype(sub: Function.Argument, sup: Function.Argument) -> bool:
            if not self.is_subtype(sub.type, sup.type):
                return False
            if not sup.required and sub.required:
                return False
            return True

        for arg1 in pos1:
            arg2: Function.Argument
            if arg1.pos < len(pos2):
                arg2 = pos2[arg1.pos]
            elif arg1.pos in mixed_by_pos:
                arg2 = mixed_by_pos[arg1.pos]
            elif not arg1.required:
                continue
            else:
                return False
            if not is_arg_subtype(arg2, arg1):
                return False

        for name, arg1 in kw1.items():
            arg2: Function.Argument
            if name in kw2:
                arg2 = kw2[name]
            elif name in mixed_by_name:
                arg2 = mixed_by_name[name]
            elif not arg1.required:
                continue
            else:
                return False
            if not is_arg_subtype(arg2, arg1):
                return False

        for arg1 in mixed1:
            pos_arg2: Optional[Function.Argument] = None
            kw_arg2: Optional[Function.Argument] = None
            if arg1.name in kw2:
                kw_arg2 = kw2[arg1.name]
            elif arg1.name in mixed_by_name:
                kw_arg2 = mixed_by_name[arg1.name]
            if arg1.pos < len(pos2):
                pos_arg2 = pos2[arg1.pos]
            elif arg1.pos in mixed_by_pos:
                pos_arg2 = mixed_by_pos[arg1.pos]

            # No match in func2 and arg is required
            if pos_arg2 is None and kw_arg2 is None and arg1.required:
                return False

            # Matching keyword argument
            if kw_arg2 is not None and not is_arg_subtype(kw_arg2, arg1):
                return False

            # Matching positional argument
            if pos_arg2 is not None and not is_arg_subtype(pos_arg2, arg1):
                return False

        mixed_positions: set[int] = {a.pos for a in mixed1}
        mixed_names: set[str] = {a.name for a in mixed1}
        for arg2 in pos2:
            if not arg2.required:
                continue
            if arg2.pos >= len(pos1) and arg2.pos not in mixed_positions:
                return False

        for name, arg2 in kw2.items():
            if not arg2.required:
                continue
            if name not in kw1 and name not in mixed_names:
                return False

        for arg2 in mixed2:
            if arg2.required:
                continue
            pos_match: bool = arg2.pos < len(pos1) or arg2.pos in mixed_positions
            kw_match: bool = arg2.name in kw1 or arg2.name in mixed_names
            if not pos_match or not kw_match:
                return False

        return True
