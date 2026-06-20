import ast
from pathlib import Path
from typing import TextIO

import click

from midas.checker.checker import TypeChecker
from midas.generator.stubs import StubsGenerator


@click.command(help="Generate stubs from Midas definitions")
@click.argument("file", type=click.File("r"))
@click.option("-o", "--output", type=click.File("w"), default="-")
def stubs(
    file: TextIO,
    output: TextIO,
):
    source_path: Path = Path(file.name).resolve()

    checker = TypeChecker()
    checker.import_midas(source_path)

    generator = StubsGenerator(checker.types)
    module: ast.Module = generator.generate_stubs()
    module = ast.fix_missing_locations(module)

    output.write(ast.unparse(module))
