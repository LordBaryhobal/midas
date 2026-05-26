from __future__ import annotations

import argparse
import difflib
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterator, Optional

from midas.ast.json_serializer import AstJsonSerializer
from midas.ast.midas import Stmt
from midas.lexer.base import MidasSyntaxError
from midas.lexer.midas import MidasLexer
from midas.lexer.token import Token
from midas.parser.midas import MidasParser

DEFAULT_BASE_DIR: Path = Path() / "tests"


@dataclass
class CaseResult:
    tokens: Optional[list[dict]] = None
    stmts: Optional[list[dict]] = None
    errors: list[dict] = field(default_factory=list)

    def dumps(self) -> str:
        return json.dumps(asdict(self), indent=2)


class Tester:
    """A test runner to check for regressions in the lexer and parser"""

    def __init__(self, base_dir: Path):
        self.base_dir: Path = base_dir

    def _list_tests(self) -> list[Path]:
        return list(self.base_dir.rglob("*.midas"))

    def run_all_tests(self) -> bool:
        paths: list[Path] = self._list_tests()
        return self.run_tests(paths)

    def run_tests(self, tests: list[Path]) -> bool:
        rule: str = "-" * 80
        n: int = len(tests)
        successes: int = 0
        failures: int = 0

        print(rule)
        for i, test in enumerate(tests):
            print(f"Case {i+1}/{n}: {test}")
            success: bool = self._run_test(test)
            if success:
                successes += 1
            else:
                failures += 1

        print(rule)
        print(f"Success: {successes}/{n}")
        print(f"Failed: {failures}/{n}")
        print(rule)
        return failures == 0

    def _run_test(self, path: Path) -> bool:
        result: CaseResult = self._exec_case(path)
        result_path: Path = self._result_path(path)
        expected: str = result_path.read_text()
        actual: str = result.dumps()

        if expected == actual:
            return True

        diff = difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile="Snapshot",
            tofile="Result",
        )
        self._print_diff(diff)
        return False

    def _exec_case(self, path: Path) -> CaseResult:
        if not path.exists():
            raise FileNotFoundError(f"Could not find test '{path}'")
        if not path.is_file():
            raise TypeError(f"Test '{path}' is not a file")

        result: CaseResult = CaseResult()
        content: str = path.read_text()
        lexer: MidasLexer = MidasLexer(content)
        tokens: list[Token] = []
        try:
            tokens = lexer.process()
            result.tokens = [
                {
                    "type": token.type.name,
                    "lexeme": token.lexeme,
                    "line": token.position.line,
                    "column": token.position.column,
                }
                for token in tokens
            ]
        except MidasSyntaxError as e:
            result.errors.append(
                {
                    "type": "SyntaxError",
                    "line": e.pos.line,
                    "column": e.pos.column,
                    "message": e.message,
                }
            )
            return result

        parser: MidasParser = MidasParser(tokens)
        stmts: list[Stmt] = parser.parse()
        result.stmts = AstJsonSerializer().serialize(stmts)
        result.errors.extend(
            [
                {
                    "line": e.token.position.line,
                    "column": e.token.position.column,
                    "message": e.message,
                }
                for e in parser.errors
            ]
        )
        return result

    def update_all_tests(self):
        paths: list[Path] = self._list_tests()
        return self.update_tests(paths)

    def update_tests(self, tests: list[Path]):
        updated: int = 0
        for test in tests:
            if self._update_test(test):
                updated += 1
        print(f"Updated {updated}/{len(tests)} tests")

    def _update_test(self, path: Path) -> bool:
        result: CaseResult = self._exec_case(path)
        result_path: Path = self._result_path(path)
        current: str = result_path.read_text()
        new: str = result.dumps()
        if current == new:
            return False
        result_path.write_text(new)
        return True

    def _result_path(self, test_path: Path) -> Path:
        return test_path.parent / (test_path.name + ".ref.json")

    def _print_diff(self, diff: Iterator[str]):
        for line in diff:
            if line.startswith("+") and not line.startswith("+++"):
                print(f"\033[92m{line}\033[0m", end="")
            elif line.startswith("-") and not line.startswith("---"):
                print(f"\033[91m{line}\033[0m", end="")
            else:
                print(line, end="")
        print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-D",
        "--base-dir",
        help="Base directory containing test files",
        type=Path,
        default=DEFAULT_BASE_DIR,
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    update = subparsers.add_parser("update")
    update.add_argument("-a", "--all", action="store_true")
    update.add_argument("FILE", type=Path, nargs="*")

    run = subparsers.add_parser("run")
    run.add_argument("-a", "--all", action="store_true")
    run.add_argument("FILE", type=Path, nargs="*")
    args = parser.parse_args()

    tester: Tester = Tester(args.base_dir)

    match args.subcommand:
        case "update":
            if args.all:
                tester.update_all_tests()
            else:
                tester.update_tests(args.FILE)
        case "run":
            success: bool
            if args.all:
                success = tester.run_all_tests()
            else:
                success = tester.run_tests(args.FILE)
            if not success:
                sys.exit(1)


if __name__ == "__main__":
    main()
