import ast
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import midas.ast.python as p
from midas.checker.checker import TypeChecker
from midas.checker.diagnostic import Diagnostic
from midas.checker.types import Type
from midas.lexer.token import TokenType
from tests.base import Tester
from tests.serializer.python import PythonAstJsonSerializer


class CustomEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ast.AST):
            return ast.dump(o)
        if isinstance(o, TokenType):
            return o.name
        return super().default(o)


@dataclass
class CaseResult:
    diagnostics: list[dict] = field(default_factory=list)
    judgments: list = field(default_factory=list)

    def dumps(self) -> str:
        return json.dumps(asdict(self), indent=2, cls=CustomEncoder)


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

        result: CaseResult = CaseResult()

        checker = TypeChecker()
        types_path: Path = path.with_suffix(".midas")
        if types_path.exists():
            checker.import_midas(types_path)

        checker.type_check(path)

        diagnostics: list[Diagnostic] = checker.diagnostics
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

        judgements: list[tuple[p.Expr, Type]] = checker.python_typer.judgements
        serializer = PythonAstJsonSerializer()
        for expr, type in judgements:
            loc = expr.location
            result.judgments.append(
                {
                    "location": {
                        "from": f"L{loc.lineno}:{loc.col_offset}",
                        "to": f"L{loc.end_lineno}:{loc.end_col_offset}",
                    },
                    "expr": expr.accept(serializer),
                    "type": asdict(type),
                }
            )

        return result


if __name__ == "__main__":
    CheckerTester.main()
