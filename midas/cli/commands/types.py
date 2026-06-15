# **Print judgements**
# ```shell
# midas types <file.py> [--types <file.midas>]
# ```

from pathlib import Path
from typing import Optional, TextIO

import click

from midas.checker.checker import TypeChecker
from midas.checker.diagnostic import Diagnostic, DiagnosticType
from midas.cli.highlighter import DiagnosticsHighlighter
from midas.cli.utils import DiagnosticPrinter


@click.command(help="Print typing judgements")
@click.argument("file", type=click.File("r"))
@click.option("-t", "--types", type=click.File("r"), multiple=True)
@click.option("-l", "--highlight", type=click.File("w"))
def types(
    file: TextIO,
    types: tuple[TextIO],
    highlight: Optional[TextIO],
):
    source_path: Path = Path(file.name).resolve()

    checker = TypeChecker()
    for types_file in types:
        checker.import_midas(Path(types_file.name).resolve())

    checker.type_check(source_path)

    diagnostics: list[Diagnostic] = []
    for expr, type in checker.python_typer.judgements:
        diagnostics.append(
            Diagnostic(
                file_path=str(source_path),
                location=expr.location,
                type=DiagnosticType.INFO,
                message=f"Type: {type}",
            )
        )
    printer = DiagnosticPrinter()
    printer.print_all(diagnostics)

    if highlight is not None:
        source: str = file.read()
        highlighter = DiagnosticsHighlighter(source)
        highlighter.highlight(diagnostics)
        highlighter.dump(highlight)
