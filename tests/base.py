from __future__ import annotations

import argparse
import difflib
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Protocol

from midas.cli.ansi import Ansi


class CaseResult(Protocol):
    def dumps(self) -> str: ...


@dataclass
class TestsSummary:
    tests: list[tuple[str, bool]] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return all(map(lambda t: t[1], self.tests))

    @property
    def successes(self) -> int:
        return sum(map(lambda t: int(t[1]), self.tests))

    @property
    def failures(self) -> int:
        return len(self.tests) - self.successes

    def add(self, name: str, success: bool):
        self.tests.append((name, success))

    @staticmethod
    def concat(*summaries: TestsSummary) -> TestsSummary:
        return TestsSummary(
            tests=sum(
                map(lambda s: s.tests, summaries),
                start=[],
            ),
        )

    def print(self):
        print("Tests summary:")
        tests: list[tuple[str, bool]] = sorted(self.tests, key=lambda t: t[0])
        for test, success in tests:
            print(f" - [{'.' if success else 'X'}] {test}")
        print("-" * 20)
        print(f"passed: {self.successes}, failed: {self.failures}")


class Tester(ABC):
    """A test runner to check for regressions in the lexer and parser"""

    CASES_DIR: Path = Path(__file__).parent / "cases"

    @property
    @abstractmethod
    def namespace(self) -> str: ...

    @property
    def extension(self) -> str:
        return "json"

    @property
    def base_dir(self) -> Path:
        return self.CASES_DIR / self.namespace

    @abstractmethod
    def _list_tests(self) -> list[Path]: ...

    def run_all_tests(self) -> TestsSummary:
        paths: list[Path] = sorted(self._list_tests())
        return self.run_tests(paths)

    def run_tests(self, tests: list[Path]) -> TestsSummary:
        rule: str = "-" * 80
        n: int = len(tests)

        summary: TestsSummary = TestsSummary()

        print(rule)
        for i, test in enumerate(tests):
            path: Path = test.resolve().relative_to(self.CASES_DIR)
            print(f"{Ansi.FG(Ansi.BRIGHT_CYAN)}Case {i+1}/{n}: {path}{Ansi.RESET}")
            success: bool = self._run_test(test)
            summary.add(str(path), success)

        print(rule)
        print(f"Success: {summary.successes}/{n}")
        print(f"Failed: {summary.failures}/{n}")
        print(rule)
        return summary

    def _run_test(self, path: Path) -> bool:
        result_path: Path = self._result_path(path)
        if not result_path.exists():
            print("Missing snapshot. Please run the update command first")
            return False
        print(Ansi.DIM, end="")
        result: CaseResult = self._exec_case(path)
        print(Ansi.RESET, end="")
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
        paths: list[Path] = sorted(self._list_tests())
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
        return test_path.parent / (test_path.name + f".ref.{self.extension}")

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
                summary: TestsSummary
                if args.all:
                    summary = tester.run_all_tests()
                else:
                    summary = tester.run_tests(args.FILE)
                if not summary.success:
                    summary.print()
                    sys.exit(1)
            case None:
                summary: TestsSummary = tester.run_all_tests()
                if not summary.success:
                    summary.print()
                    sys.exit(1)
            case _:
                print(f"Unknown subcommand '{args.subcommand}'")
                sys.exit(1)
