# **Compile source**
# ```shell
# midas compile <file.py> [--types <file.midas>] [-o <output>] [--assertions|--strict|--no-checks]
# ```

import sys
from pathlib import Path
from typing import Optional, TextIO

import click

from midas.checker.checker import TypeChecker
from midas.checker.diagnostic import Diagnostic, DiagnosticType
from midas.cli.utils import DiagnosticPrinter
from midas.generator.generator import Generator
from midas.utils import TypedAST


@click.command(help="Compile source")
@click.argument("file", type=click.File("r"))
@click.option("-t", "--types", type=click.File("r"), multiple=True)
@click.option("-s", "--stubs", type=str, multiple=True)
@click.option("--ignore-errors", is_flag=True)
def compile(
    file: TextIO,
    types: tuple[TextIO],
    stubs: tuple[str],
    ignore_errors: bool,
):
    source: str = file.read()
    source_path: Path = Path(file.name).resolve()

    checker = TypeChecker()
    type_files: list[tuple[Path, Optional[str]]] = []
    for i, types_file in enumerate(types):
        in_path: Path = Path(types_file.name).resolve()
        checker.import_midas(in_path)
        type_files.append((in_path, stubs[i] if i < len(stubs) else None))

    typed_ast: TypedAST = checker.type_check_source(source, str(source_path))
    diagnostics: list[Diagnostic] = checker.diagnostics.copy()
    printer = DiagnosticPrinter()
    printer.print_all(diagnostics)

    if not ignore_errors and any(
        map(lambda d: d.type == DiagnosticType.ERROR, diagnostics)
    ):
        sys.exit(1)

    generator = Generator(workdir=source_path.parent, types=checker.types)
    generator.generate(typed_ast, source_path, type_files=type_files)
