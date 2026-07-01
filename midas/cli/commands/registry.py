# **Dump types registry**
# ```shell
# midas dump-registry [--types <file.midas>]
# ```

from pathlib import Path
from typing import TextIO

import click

from midas.ast.printer import MidasPrinter
from midas.checker.checker import TypeChecker
from midas.checker.registry import Member
from midas.checker.types import AppliedType, BaseType, DerivedType, GenericType, Type


def base_type(type: Type) -> Type:
    match type:
        case BaseType():
            return type
        case DerivedType(type=base):
            return base
        case AppliedType(body=body):
            return body
        case GenericType(body=body):
            return body
        case _:
            return type


@click.command(help="Dump types registry")
@click.option("-t", "--types", type=click.File("r"), multiple=True)
def dump_registry(
    types: tuple[TextIO],
):
    checker = TypeChecker()
    for types_file in types:
        checker.import_midas(Path(types_file.name).resolve())

    print("##### Types #####")
    for name, type in checker.types._types.items():
        members: dict[str, Member] = checker.types._members.get(name, {})
        params: str = ""
        if isinstance(type, GenericType):
            params = ", ".join(map(str, type.params))
            params = f"[{params}]"
        print(f"{name}{params} = {base_type(type)}")
        if len(members) != 0:
            print(" " * 4 + "Members:")
            for member_name, member in members.items():
                kind: str = member.kind.name
                print(" " * 8 + f"({kind:8}) {member_name}: {member.type}")

    print("##### Predicates #####")
    printer = MidasPrinter()
    for name, predicate in checker.types._predicates.items():
        body: str = printer.print(predicate.body)
        if predicate.alias:
            print(f"{name}: {predicate.type} = {body}")
        else:
            print(f"{name}{predicate.type}:")
            body = "\n".join(
                "    " + ("return " if i == 0 else "") + line
                for i, line in enumerate(body.split("\n"))
            )
            print(body)
