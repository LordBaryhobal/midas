import ast
from dataclasses import dataclass
from pathlib import Path

from midas.checker.checker import TypeChecker
from midas.checker.diagnostic import DiagnosticType
from midas.generator.generator import Generator
from midas.utils import TypedAST
from tests.base import Tester


@dataclass
class CaseResult:
    compiled_ast: ast.AST = ast.Module([], [])

    def dumps(self) -> str:
        return ast.dump(self.compiled_ast, indent=2)


class GeneratorTester(Tester):
    @property
    def namespace(self) -> str:
        return "generator"

    @property
    def extension(self) -> str:
        return "txt"

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

        typed_ast: TypedAST = checker.type_check(path)

        if not any(d.type == DiagnosticType.ERROR for d in checker.diagnostics):
            generator = Generator(workdir=path.parent)
            result.compiled_ast = generator.generate_ast(typed_ast, path)

        return result


if __name__ == "__main__":
    GeneratorTester.main()
