from pathlib import Path
from typing import Optional

from midas.checker.diagnostic import Diagnostic
from midas.checker.midas import MidasTyper
from midas.checker.python import PythonTyper
from midas.checker.registry import TypesRegistry
from midas.checker.reporter import Reporter
from midas.utils import TypedAST


class TypeChecker:
    def __init__(self):
        self.types: TypesRegistry = TypesRegistry()
        self.reporter: Reporter = Reporter()

        self.midas_typer = MidasTyper(self.types, self.reporter)
        self.python_typer = PythonTyper(self.types, self.reporter)

    def import_midas(self, path: Path):
        source: str = path.read_text()
        return self.import_midas_source(source, path=str(path))

    def import_midas_source(self, source: str, path: Optional[str] = None):
        self.midas_typer.process(source, path)

    def type_check(self, path: Path) -> TypedAST:
        source: str = path.read_text()
        return self.type_check_source(source, path=str(path))

    def type_check_source(self, source: str, path: Optional[str] = None) -> TypedAST:
        return self.python_typer.process(source, path)

    @property
    def diagnostics(self) -> list[Diagnostic]:
        return self.reporter.diagnostics
