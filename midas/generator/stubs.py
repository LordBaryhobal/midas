import ast
from typing import Optional

import midas.ast.midas as m
from midas.checker.registry import Member, TypesRegistry
from midas.checker.types import (
    AliasType,
    AppliedType,
    BaseType,
    ComplexType,
    ExtensionType,
    Function,
    GenericType,
    OverloadedFunction,
    TopType,
    Type,
    TypeVar,
    UnitType,
    UnknownType,
    substitute_typevars,
)

Empty = ast.Constant(value=...)


class StubsGenerator:
    def __init__(self, types: TypesRegistry) -> None:
        self.types: TypesRegistry = types
        self.stubs: list[ast.stmt] = []
        self.typing_imports: set[str] = set()
        self.protocol_idx: int = 0
        self.stub_idx: int = 0
        self.type_var_idx: int = 0
        self.substitutions: dict[str, dict[str, Type]] = {}

    def generate_stubs(self) -> ast.Module:
        self.stubs = []
        self.typing_imports = set()
        for name, type in self.types._types.items():
            self.generate_stub(name, type)

        imports = [
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
        return ast.Module(body=imports + self.stubs, type_ignores=[])

    def generate_stub(self, name: str, type: Type):
        base_type: Type = type

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
        match type:
            case AliasType(type=base):
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
            case _:
                return [], {}

    def generate_body(
        self, members: dict[str, Member], substitutions: dict[str, Type]
    ) -> list[ast.stmt]:
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
        match type:
            case AliasType(name=name) | GenericType(name=name) if (
                name in self.substitutions
            ):
                type = substitute_typevars(type, self.substitutions[name])

        match type:
            case TopType() | UnknownType():
                self.add_typing_import("Any")
                return ast.Name(id="Any")
            case BaseType(name=name):
                return ast.Name(id=name)
            case AliasType(name=name):
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

            case ComplexType():
                name: str = self.new_stub_name()
                self.generate_stub(name, type)
                return ast.Name(id=name)

            case ExtensionType():
                raise NotImplementedError

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

    def dump_method(
        self, name: str, method: Type, overloaded: bool = False
    ) -> list[ast.stmt]:
        match method:
            case Function():
                if overloaded:
                    self.add_typing_import("overload")
                return [
                    ast.FunctionDef(
                        name=name,
                        args=self.dump_args(method, with_self=True),
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

    def dump_args(self, func: Function, with_self: bool = False) -> ast.arguments:
        pos: list[ast.arg] = [
            ast.arg(arg=f"_{arg.pos}", annotation=self.dump_type(arg.type))
            for arg in func.pos_args
        ]
        mixed: list[ast.arg] = [
            ast.arg(arg=arg.name, annotation=self.dump_type(arg.type))
            for arg in func.args
        ]
        kw: list[ast.arg] = [
            ast.arg(arg=arg.name, annotation=self.dump_type(arg.type))
            for arg in func.kw_args
        ]
        defaults: list[ast.expr] = [
            Empty for arg in func.pos_args + func.args if not arg.required
        ]
        kw_defaults: list[Optional[ast.expr]] = [
            None if arg.required else Empty for arg in func.kw_args
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
        self.add_typing_import("Protocol")
        name: str = self.new_protocol_name()
        protocol = ast.ClassDef(
            name=name,
            bases=[ast.Name(id="Protocol")],
            keywords=[],
            body=[
                ast.FunctionDef(
                    name="__call__",
                    args=self.dump_args(func, with_self=True),
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
        name: str = f"_Protocol{self.protocol_idx}"
        self.protocol_idx += 1
        return name

    def new_stub_name(self) -> str:
        name: str = f"_Stub_{self.stub_idx}"
        self.stub_idx += 1
        return name

    def new_type_var_name(self) -> str:
        name: str = f"_T{self.type_var_idx}"
        self.type_var_idx += 1
        return name

    def add_stub(self, stub: ast.stmt):
        self.stubs.append(stub)

    def add_typing_import(self, name: str):
        self.typing_imports.add(name)

    def define_type_vars(self, vars: list[TypeVar]) -> list[TypeVar]:
        vars2: list[TypeVar] = []
        for var in vars:
            vars2.append(self.define_type_var(var))
        return vars2

    def define_type_var(self, var: TypeVar) -> TypeVar:
        name: str = self.new_type_var_name()
        self.add_typing_import("TypeVar")
        self.add_stub(
            ast.Assign(
                targets=[ast.Name(id=name)],
                value=ast.Call(
                    func=ast.Name(id="TypeVar"),
                    args=[
                        ast.Constant(value=name),
                    ],
                    keywords=(
                        []
                        if var.bound is None
                        else [
                            ast.keyword(
                                arg="bound",
                                value=self.dump_type(var.bound),
                            )
                        ]
                    ),
                ),
            )
        )
        return TypeVar(name=name, bound=None)
