import ast
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import midas.ast.python as p
from midas.checker.checker import Checker
from midas.checker.diagnostic import Diagnostic
from midas.parser.python import PythonParser
from midas.resolver.resolver import Resolver
from tests.base import Tester


@dataclass
class CaseResult:
    diagnostics: list[dict] = field(default_factory=list)

    def dumps(self) -> str:
        return json.dumps(asdict(self), indent=2)


class CheckerTester(Tester):
    @property
    def namespace(self) -> str:
        return "checker"

    def _list_tests(self) -> list[Path]:
        return list(self.base_dir.rglob("*.py"))

    def _exec_case(self, path: Path) -> CaseResult:
        if not path.exists():
            raise FileNotFoundError(f"Could not find test '{path}'")
        if not path.is_file():
            raise TypeError(f"Test '{path}' is not a file")

        source: str = path.read_text()
        tree: ast.Module = ast.parse(source, filename=path)
        parser = PythonParser()
        stmts: list[p.Stmt] = parser.parse_module(tree)
        resolver = Resolver()
        resolver.resolve(*stmts)
        result: CaseResult = CaseResult()
        checker = Checker(resolver.locals, file_path=path)
        diagnostics: list[Diagnostic] = checker.check(stmts)
        for diagnostic in diagnostics:
            result.diagnostics.append(
                {
                    "type": str(diagnostic.type),
                    "location": {
                        "start": (
                            diagnostic.location.lineno,
                            diagnostic.location.col_offset,
                        ),
                        "end": (
                            diagnostic.location.end_lineno,
                            diagnostic.location.end_col_offset,
                        ),
                    },
                    "message": diagnostic.message,
                }
            )

        return result


if __name__ == "__main__":
    CheckerTester.main()
