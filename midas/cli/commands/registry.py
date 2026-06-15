# **Dump types registry**
# ```shell
# midas dump-registry [--types <file.midas>]
# ```

from pathlib import Path
from typing import TextIO

import click

from midas.checker.checker import TypeChecker
from midas.checker.types import Type


@click.command()
@click.option("-t", "--types", type=click.File("r"), multiple=True)
def dump_registry(
    types: tuple[TextIO],
):
    checker = TypeChecker()
    for types_file in types:
        checker.import_midas(Path(types_file.name).resolve())

    for name, type in checker.types._types.items():
        members: dict[str, Type] = checker.types._members.get(name, {})
        print(f"{name} = {type}")
        if len(members) != 0:
            print(" " * 4 + "Members:")
            for member_name, member_type in members.items():
                print(" " * 8 + f"{member_name}: {member_type}")
