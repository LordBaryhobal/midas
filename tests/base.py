from __future__ import annotations

import argparse
import difflib
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator, Protocol


class CaseResult(Protocol):
    def dumps(self) -> str: ...


class Tester(ABC):
    """A test runner to check for regressions in the lexer and parser"""

    CASES_DIR: Path = Path(__file__).parent / "cases"

    @property
    @abstractmethod
    def namespace(self) -> str: ...

    @property
    def base_dir(self) -> Path:
        return self.CASES_DIR / self.namespace

    @abstractmethod
    def _list_tests(self) -> list[Path]: ...

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
            print(f"Case {i+1}/{n}: {test.relative_to(self.CASES_DIR)}")
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
        result_path: Path = self._result_path(path)
        if not result_path.exists():
            print("Missing snapshot. Please run the update command first")
            return False
        result: CaseResult = self._exec_case(path)
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

    @abstractmethod
    def _exec_case(self, path: Path) -> CaseResult: ...

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
        current: str = result_path.read_text() if result_path.exists() else ""
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

    @classmethod
    def main(cls):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="subcommand")

        update = subparsers.add_parser("update")
        update.add_argument("-a", "--all", action="store_true")
        update.add_argument("FILE", type=Path, nargs="*")

        run = subparsers.add_parser("run")
        run.add_argument("-a", "--all", action="store_true")
        run.add_argument("FILE", type=Path, nargs="*")
        args = parser.parse_args()

        tester: Tester = cls()

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
