import ast
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from midas.ast.python import Stmt
from midas.parser.python import PythonParser
from tests.base import Tester
from tests.serializer.python import PythonAstJsonSerializer


@dataclass
class CaseResult:
    stmts: Optional[list[dict]] = None

    def dumps(self) -> str:
        return json.dumps(asdict(self), indent=2)


class PythonTester(Tester):
    @property
    def namespace(self) -> str:
        return "python-parser"

    def _list_tests(self) -> list[Path]:
        return list(self.base_dir.rglob("*.py"))

    def _exec_case(self, path: Path) -> CaseResult:
        if not path.exists():
            raise FileNotFoundError(f"Could not find test '{path}'")
        if not path.is_file():
            raise TypeError(f"Test '{path}' is not a file")

        result: CaseResult = CaseResult()
        content: str = path.read_text()
        tree: ast.Module = ast.parse(content)

        parser: PythonParser = PythonParser()
        stmts: list[Stmt] = parser.parse_module(tree)
        result.stmts = PythonAstJsonSerializer().serialize(stmts)
        return result


if __name__ == "__main__":
    PythonTester.main()
