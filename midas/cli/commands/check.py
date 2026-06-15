# **Run type checker and report diagnostics**
# ```shell
# midas check <file.py> [--types <file.midas>]
# ```

from pathlib import Path
from typing import Optional, TextIO

import click

from midas.checker.checker import TypeChecker
from midas.checker.diagnostic import Diagnostic
from midas.cli.highlighter import DiagnosticsHighlighter
from midas.cli.utils import DiagnosticPrinter


@click.command(help="Run type checker and report diagnostics")
@click.argument("file", type=click.File("r"))
@click.option("-t", "--types", type=click.File("r"), multiple=True)
@click.option("-l", "--highlight", type=click.File("w"))
def check(
    file: TextIO,
    types: tuple[TextIO],
    highlight: Optional[TextIO],
):
    source_path: Path = Path(file.name).resolve()

    checker = TypeChecker()
    for types_file in types:
        checker.import_midas(Path(types_file.name).resolve())

    checker.type_check(source_path)
    diagnostics: list[Diagnostic] = checker.diagnostics.copy()
    printer = DiagnosticPrinter()
    printer.print_all(diagnostics)

    if highlight is not None:
        source: str = file.read()
        highlighter = DiagnosticsHighlighter(source)
        highlighter.highlight(diagnostics)
        highlighter.dump(highlight)
