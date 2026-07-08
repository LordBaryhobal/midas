import sys
from typing import Type

from midas.cli.ansi import Ansi
from tests.base import Tester, TestsSummary
from tests.checker import CheckerTester
from tests.generator import GeneratorTester
from tests.midas import MidasTester
from tests.python import PythonTester


def print_banner(name: str):
    horizontal: str = "+" + "-" * (len(name) + 2) + "+"
    print(horizontal)
    print(f"| {name} |")
    print(horizontal)


def run_tests(tester_cls: Type[Tester]) -> TestsSummary:
    print_banner(tester_cls.__name__)
    tester: Tester = tester_cls()
    summary: TestsSummary = tester.run_all_tests()
    print()
    return summary


def main():
    testers: list[Type[Tester]] = [
        PythonTester,
        MidasTester,
        CheckerTester,
        GeneratorTester,
    ]

    summaries: list[TestsSummary] = list(
        map(run_tests, testers)
    )  # list to avoid early stop
    summary: TestsSummary = TestsSummary.concat(*summaries)

    if summary.success:
        print(Ansi.FG(Ansi.BRIGHT_GREEN) + "All tests passed!" + Ansi.RESET)
    else:
        print(Ansi.FG(Ansi.BRIGHT_RED) + "Some tests failed!" + Ansi.RESET)
        summary.print()
        sys.exit(1)


if __name__ == "__main__":
    main()
