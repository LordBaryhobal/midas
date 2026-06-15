# **Validate midas definitions**
# ```shell
# midas validate <file.midas>
# ```

from pathlib import Path
from typing import Optional, TextIO

import click

from midas.checker.checker import TypeChecker
from midas.checker.diagnostic import Diagnostic
from midas.cli.highlighter import DiagnosticsHighlighter
from midas.cli.utils import DiagnosticPrinter


@click.command()
@click.argument("file", type=click.File("r"))
@click.option("-l", "--highlight", type=click.File("w"))
def validate(
    file: TextIO,
    highlight: Optional[TextIO],
):
    source_path: Path = Path(file.name).resolve()

    checker = TypeChecker()
    checker.import_midas(source_path)

    diagnostics: list[Diagnostic] = checker.diagnostics.copy()
    printer = DiagnosticPrinter()
    printer.print_all(diagnostics)

    if highlight is not None:
        source: str = file.read()
        highlighter = DiagnosticsHighlighter(source)
        highlighter.highlight(diagnostics)
        highlighter.dump(highlight)
