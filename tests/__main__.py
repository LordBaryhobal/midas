from typing import Type

from midas.cli.ansi import Ansi
from tests.base import Tester
from tests.checker import CheckerTester
from tests.generator import GeneratorTester
from tests.midas import MidasTester
from tests.python import PythonTester


def print_banner(name: str):
    horizontal: str = "+" + "-" * (len(name) + 2) + "+"
    print(horizontal)
    print(f"| {name} |")
    print(horizontal)


def run_tests(tester_cls: Type[Tester]) -> bool:
    print_banner(tester_cls.__name__)
    tester: Tester = tester_cls()
    success: bool = tester.run_all_tests()
    print()
    return success


def main():
    testers: list[Type[Tester]] = [
        PythonTester,
        MidasTester,
        CheckerTester,
        GeneratorTester,
    ]

    success: bool = all(list(map(run_tests, testers)))  # list to avoid early stop

    if success:
        print(Ansi.FG(Ansi.BRIGHT_GREEN) + "All tests passed!" + Ansi.RESET)
    else:
        print(Ansi.FG(Ansi.BRIGHT_RED) + "Some tests failed!" + Ansi.RESET)


if __name__ == "__main__":
    main()
