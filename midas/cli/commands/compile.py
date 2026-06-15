# **Compile source**
# ```shell
# midas compile <file.py> [--types <file.midas>] [-o <output>] [--assertions|--strict|--no-checks]
# ```

from pathlib import Path
from typing import TextIO

import click

from midas.checker.checker import TypeChecker
from midas.checker.diagnostic import Diagnostic
from midas.cli.utils import DiagnosticPrinter
from midas.generator.generator import Generator
from midas.utils import TypedAST


@click.command()
@click.argument("file", type=click.File("r"))
@click.option("-t", "--types", type=click.File("r"), multiple=True)
def compile(
    file: TextIO,
    types: tuple[TextIO],
):
    source: str = file.read()
    source_path: Path = Path(file.name).resolve()

    checker = TypeChecker()
    for types_file in types:
        checker.import_midas(Path(types_file.name).resolve())

    typed_ast: TypedAST = checker.type_check_source(source, str(source_path))
    diagnostics: list[Diagnostic] = checker.diagnostics.copy()
    printer = DiagnosticPrinter()
    printer.print_all(diagnostics)

    generator = Generator(workdir=source_path.parent)
    generator.generate(typed_ast, source_path)
