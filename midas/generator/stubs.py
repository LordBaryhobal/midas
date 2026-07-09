import ast
from typing import Optional, assert_never

import midas.ast.midas as m
from midas.checker.registry import Member, TypesRegistry
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
    OverloadedFunction,
    ParamSpec,
    TopType,
    TupleType,
    Type,
    TypeVar,
    UnitType,
    UnknownType,
    Variance,
    substitute_typevars,
)

Empty = ast.Constant(value=...)


class StubsGenerator:
    """A class to generate Python stubs for user-defined Midas types"""

    def __init__(self, types: TypesRegistry) -> None:
        self.types: TypesRegistry = types
        self.stubs: list[ast.stmt] = []
        self.typing_imports: set[str] = set()
        self.import_pandas: bool = False
        self.protocol_idx: int = 0
        self.stub_idx: int = 0
        self.type_var_idx: int = 0
        self.substitutions: dict[str, dict[str, Type]] = {}

    def generate_stubs(self) -> ast.Module:
        """Generate a Python module of stubs for all user-defined types

        Returns:
            ast.Module: the generated module
        """
        self.stubs = []
        self.typing_imports = set()
        self.import_pandas = False
        for name, type in self.types._types.items():
            # Skip builtin types, not just based on name so the user can override
            # TODO: check if added members on builtin type, or prevent it
            match type:
                case BaseType(name=name_) if name == name_:
                    continue
                case GenericType(
                    name=name1,
                    body=BaseType(name=name2),
                ) if (
                    name == name1 == name2
                ):
                    continue
            self.generate_stub(name, type)

        imports: list[ast.stmt] = [
            ast.ImportFrom(
                module="__future__",
                names=[ast.alias(name="annotations")],
                level=0,
            )
        ]
        if len(self.typing_imports) != 0:
            imports.append(
                ast.ImportFrom(
                    module="typing",
                    names=[
                        ast.alias(name=name) for name in sorted(self.typing_imports)
                    ],
                    level=0,
                )
            )
        if self.import_pandas:
            imports.append(
                ast.Import(
                    names=[
                        ast.alias(
                            name="pandas",
                            asname="pd",
                        )
                    ],
                )
            )
        return ast.Module(body=imports + self.stubs, type_ignores=[])

    def generate_stub(self, name: str, type: Type):
        """Generate a stub for the given type

        Args:
            name (str): the name of the type
            type (Type): the type
        """
        base_type: Type = type

        # Generate simple assignment for type aliases
        # A type alias will have a name that is different from the type represents
        # or will neither be a `DeriveType` nor a `GenericType`
        match type:
            case DerivedType(name=name_) | GenericType(name=name_) if name_ == name:
                pass
            case UnitType() if name == "None":
                pass
            case TopType() if name == "Any":
                pass
            case _:
                alias = ast.Assign(
                    targets=[ast.Name(id=name)], value=self.dump_type(type)
                )
                self.add_stub(alias)
                return

        members: dict[str, Member] = self.types._members.get(name, {})
        if isinstance(base_type, (BaseType, TopType, UnitType)) and len(members) == 0:
            return

        bases: list[ast.expr] = []
        substitutions: dict[str, Type] = {}
        bases, substitutions = self.get_bases(type)
        self.substitutions[name] = substitutions

        body = self.generate_body(members, substitutions)
        stub = ast.ClassDef(
            name=name,
            bases=bases,
            body=body,
            keywords=[],
            decorator_list=[],
        )
        self.add_stub(stub)

    def get_bases(self, type: Type) -> tuple[list[ast.expr], dict[str, Type]]:
        """Get the list of class bases and type parameter substitutions for a type

        Args:
            type (Type): the type whose bases to get

        Returns:
            tuple[list[ast.expr], dict[str, Type]]: a tuple containing the list
                of class bases (already translated to Python AST nodes), and a
                mapping of type parameter substitutions (to replace them with
                their generated aliases)
        """
        match type:
            case DerivedType(type=base):
                return [self.dump_type(base)], {}

            case GenericType(params=params, body=body):
                self.add_typing_import("Generic")
                type_vars: ast.expr

                params2: list[TypeVar] = self.define_type_vars(params)
                if len(params) == 1:
                    type_vars = ast.Name(id=params2[0].name)
                else:
                    type_vars = ast.Tuple(
                        elts=[ast.Name(id=param.name) for param in params2]
                    )

                substitutions: dict[str, TypeVar] = {
                    param.name: param2 for param, param2 in zip(params, params2)
                }

                body_bases, body_subsitutions = self.get_bases(body)
                return (
                    body_bases
                    + [
                        ast.Subscript(
                            value=ast.Name(id="Generic"),
                            slice=type_vars,
                        )
                    ],
                    body_subsitutions | substitutions,
                )

            case ConstraintType(type=base):
                return self.get_bases(base)

            case TypeVar(bound=bound) if bound is not None:
                return [self.dump_type(bound)], {}

            case _:
                return [], {}

    def generate_body(
        self, members: dict[str, Member], substitutions: dict[str, Type]
    ) -> list[ast.stmt]:
        """Generate a class body given its members

        Args:
            members (dict[str, Member]): the class members
            substitutions (dict[str, Type]): a mapping of type parameter
                substitutions (to replace them with their generated aliases)

        Returns:
            list[ast.stmt]: the generated class body statements
        """
        if len(members) == 0:
            return [ast.Expr(value=Empty)]

        body: list[ast.stmt] = []
        for name, member in members.items():
            type: Type = member.type
            type = substitute_typevars(type, substitutions)
            match member.kind:
                case m.MemberKind.PROPERTY:
                    body.append(
                        ast.AnnAssign(
                            target=ast.Name(id=name),
                            annotation=self.dump_type(type),
                            simple=1,
                        )
                    )
                case m.MemberKind.METHOD:
                    body.extend(self.dump_method(name, type))
        return body

    def dump_type(self, type: Type) -> ast.expr:
        """Translate a type to a Python expression

        Args:
            type (Type): the type to translate

        Returns:
            ast.expr: the generated Python expression
        """
        match type:
            case DerivedType(name=name) | GenericType(name=name) if (
                name in self.substitutions
            ):
                type = substitute_typevars(type, self.substitutions[name])

        match type:
            case TopType() | UnknownType():
                self.add_typing_import("Any")
                return ast.Name(id="Any")

            case BaseType(name=name):
                return ast.Name(id=name)

            case DerivedType(name=name):
                return ast.Name(id=name)

            case UnitType():
                return ast.Constant(value=None)

            case Function():
                name: str = self.define_protocol(type)
                return ast.Name(id=name)

            case OverloadedFunction(overloads=overloads):
                if len(overloads) == 1:
                    return self.dump_type(overloads[0])
                return ast.BinOp(
                    left=self.dump_type(OverloadedFunction(overloads=overloads[:-1])),
                    op=ast.BitOr(),
                    right=self.dump_type(overloads[-1]),
                )

            case TypeVar():
                return ast.Name(id=type.name)

            case GenericType(name=name):
                params: ast.expr
                if len(type.params) == 1:
                    params = self.dump_type(type.params[0])
                else:
                    params = ast.Tuple(
                        elts=[self.dump_type(param) for param in type.params]
                    )
                return ast.Subscript(
                    value=ast.Name(id=type.name),
                    slice=params,
                )

            case AppliedType():
                args: ast.expr
                if len(type.args) == 1:
                    args = self.dump_type(type.args[0])
                else:
                    args = ast.Tuple(elts=[self.dump_type(arg) for arg in type.args])
                return ast.Subscript(
                    value=ast.Name(id=type.name),
                    slice=args,
                )

            case ConstraintType():
                return self.dump_type(type.type)

            case TupleType(items=items):
                return ast.Subscript(
                    value=ast.Name(id="tuple"),
                    slice=ast.Tuple(
                        elts=[self.dump_type(item) for item in items],
                    ),
                )

            case ColumnType():
                self.import_pandas = True
                return ast.Attribute(
                    value=ast.Name(id="pd"),
                    attr="Series",
                )

            case DataFrameType():
                self.import_pandas = True
                return ast.Attribute(
                    value=ast.Name(id="pd"),
                    attr="DataFrame",
                )

            case FrameGroupBy():
                self.import_pandas = True
                return ast.Attribute(
                    value=ast.Attribute(
                        value=ast.Attribute(
                            value=ast.Name(id="pd"),
                            attr="api",
                        ),
                        attr="typing",
                    ),
                    attr="DataFrameGroupBy",
                )

            case ColumnGroupBy():
                self.import_pandas = True
                return ast.Attribute(
                    value=ast.Attribute(
                        value=ast.Attribute(
                            value=ast.Name(id="pd"),
                            attr="api",
                        ),
                        attr="typing",
                    ),
                    attr="SeriesGroupBy",
                )

            case _:
                assert_never(type)

    def dump_method(
        self, name: str, method: Type, overloaded: bool = False
    ) -> list[ast.stmt]:
        """Generate definitions for a method

        Args:
            name (str): the method's name
            method (Type): the method's type
            overloaded (bool, optional): whether this method is part of an
                overloaded method (used when called recursively). Defaults to False.

        Returns:
            list[ast.stmt]: the generated function definitions
        """
        match method:
            case Function():
                if overloaded:
                    self.add_typing_import("overload")
                return [
                    ast.FunctionDef(
                        name=name,
                        args=self.dump_params(method.params, with_self=True),
                        returns=self.dump_type(method.returns),
                        body=[ast.Expr(value=Empty)],
                        decorator_list=[ast.Name(id="overload")] if overloaded else [],
                    )
                ]
            case OverloadedFunction(overloads=overloads):
                stmts: list[ast.stmt] = []
                for overload in overloads:
                    stmts.extend(self.dump_method(name, overload, True))
                return stmts
            case _:
                return [
                    ast.AnnAssign(
                        target=ast.Name(id=name),
                        annotation=self.dump_type(method),
                        simple=1,
                    )
                ]

    def dump_params(self, params: ParamSpec, with_self: bool = False) -> ast.arguments:
        """Generate an `ast.arguments` node for the given parameter spec

        Args:
            params (ParamSpec): the parameter spec to translate
            with_self (bool, optional): whether to include a `self` parameter.
                Defaults to False.

        Returns:
            ast.arguments: the generate Python AST node
        """
        pos: list[ast.arg] = [
            ast.arg(
                arg=f"_{param.pos}",
                annotation=self.dump_type(param.type),
            )
            for param in params.pos
        ]
        mixed: list[ast.arg] = [
            ast.arg(
                arg=param.name,
                annotation=self.dump_type(param.type),
            )
            for param in params.mixed
        ]
        kw: list[ast.arg] = [
            ast.arg(
                arg=param.name,
                annotation=self.dump_type(param.type),
            )
            for param in params.kw
        ]
        defaults: list[ast.expr] = [
            Empty for param in params.pos + params.mixed if not param.required
        ]
        kw_defaults: list[Optional[ast.expr]] = [
            None if param.required else Empty for param in params.kw
        ]
        if with_self:
            arg = ast.arg(arg="self", annotation=None)
            if len(pos) != 0:
                pos.insert(0, arg)
            else:
                mixed.insert(0, arg)
        return ast.arguments(
            posonlyargs=pos,
            args=mixed,
            kwonlyargs=kw,
            defaults=defaults,
            kw_defaults=kw_defaults,
        )

    def define_protocol(self, func: Function) -> str:
        """Generate a :class:`Protocol` to use in a function stub

        Args:
            func (Function): the function signature to define

        Returns:
            str: the name of the generated protocol
        """
        self.add_typing_import("Protocol")
        name: str = self.new_protocol_name()
        protocol = ast.ClassDef(
            name=name,
            bases=[ast.Name(id="Protocol")],
            keywords=[],
            body=[
                ast.FunctionDef(
                    name="__call__",
                    args=self.dump_params(func.params, with_self=True),
                    returns=self.dump_type(func.returns),
                    body=[ast.Expr(value=Empty)],
                    decorator_list=[],
                ),
            ],
            decorator_list=[],
        )
        self.add_stub(protocol)
        return name

    def new_protocol_name(self) -> str:
        """Get a unique protocol name

        Returns:
            str: the unique protocol name
        """
        name: str = f"_Protocol{self.protocol_idx}"
        self.protocol_idx += 1
        return name

    def new_stub_name(self) -> str:
        """Get a unique stub name

        Returns:
            str: the unique stub name
        """
        name: str = f"_Stub_{self.stub_idx}"
        self.stub_idx += 1
        return name

    def new_type_var_name(self) -> str:
        """Get a unique type variable name

        Returns:
            str: the unique type variable name
        """
        name: str = f"_T{self.type_var_idx}"
        self.type_var_idx += 1
        return name

    def add_stub(self, stub: ast.stmt):
        """Append the given statement to the output

        Args:
            stub (ast.stmt): the statement to append
        """
        self.stubs.append(stub)

    def add_typing_import(self, name: str):
        """Add the given name to the list of names to import from `typing`

        Args:
            name (str): the name to import
        """
        self.typing_imports.add(name)

    def define_type_vars(self, vars: list[TypeVar]) -> list[TypeVar]:
        """Define aliases for the given type variables

        Args:
            vars (list[TypeVar]): the variables to define

        Returns:
            list[TypeVar]: new type variables named with the generated aliases
        """
        vars2: list[TypeVar] = []
        for var in vars:
            vars2.append(self.define_type_var(var))
        return vars2

    def define_type_var(self, var: TypeVar) -> TypeVar:
        """Define a type variable alias

        Args:
            var (TypeVar): the type variable to define

        Returns:
            TypeVar: a new type variable named with a uniquely generated alias
        """
        name: str = self.new_type_var_name()
        self.add_typing_import("TypeVar")

        kwargs: list[ast.keyword] = []
        if var.bound is not None:
            kwargs.append(
                ast.keyword(
                    arg="bound",
                    value=self.dump_type(var.bound),
                )
            )
        if var.variance == Variance.COVARIANT:
            kwargs.append(
                ast.keyword(
                    arg="covariant",
                    value=ast.Constant(value=True),
                )
            )
        elif var.variance == Variance.CONTRAVARIANT:
            kwargs.append(
                ast.keyword(
                    arg="contravariant",
                    value=ast.Constant(value=True),
                )
            )
        self.add_stub(
            ast.Assign(
                targets=[ast.Name(id=name)],
                value=ast.Call(
                    func=ast.Name(id="TypeVar"),
                    args=[
                        ast.Constant(value=name),
                    ],
                    keywords=kwargs,
                ),
            )
        )
        return TypeVar(name=name, bound=None)
