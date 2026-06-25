from collections import defaultdict
from pathlib import Path
from typing import Optional

from midas.ast.location import Location
from midas.checker.diagnostic import Diagnostic, DiagnosticType
from midas.cli.ansi import Ansi


class DiagnosticPrinter:
    COLORS: dict[DiagnosticType, int] = {
        DiagnosticType.ERROR: Ansi.RED,
        DiagnosticType.WARNING: Ansi.YELLOW,
        DiagnosticType.INFO: Ansi.CYAN,
        DiagnosticType.DEBUG: Ansi.MAGENTA,
    }

    def __init__(self) -> None:
        self.files: dict[Optional[str], list[str]] = {}

    def get_lines(self, filename: Optional[str]) -> list[str]:
        if filename is None:
            return []
        if filename not in self.files:
            path: Path = Path(filename)
            if path.exists() and path.is_file():
                self.files[filename] = path.read_text().split("\n")
            else:
                self.files[filename] = []
        return self.files[filename]

    def print_all(self, diagnostics: list[Diagnostic], indent: int = 4):
        by_type: dict[DiagnosticType, int] = defaultdict(int)
        for diagnostic in diagnostics:
            filename: Optional[str] = diagnostic.file_path
            lines = self.get_lines(filename)
            self.print(lines, diagnostic, indent=indent)
            by_type[diagnostic.type] += 1

        if len(diagnostics) == 0:
            return

        counts: list[str] = []
        for type in DiagnosticType:
            if type not in by_type:
                continue
            count: int = by_type[type]
            color: int = self.COLORS.get(type, Ansi.WHITE)
            counts.append(f"{Ansi.FG(color)}{type.value}s{Ansi.RESET}: {count}")

        print("    ".join(counts))

    def print(self, lines: list[str], diagnostic: Diagnostic, indent: int = 4):
        """Pretty-print a diagnostic, showing some context if possible

        If the diagnostic concerns a specific part of one line, the line is shown
        with the affected part highlighted. The message is clearly printed under the
        line with an underline further indicating the target expression.

        If multiple lines are concerned, no context is shown, only the
        diagnostic type, location and message

        Args:
            lines (list[str]): source code lines
            diagnostic (Diagnostic): the diagnostic to print
            indent (int, optional): the number of spaces added before the target line to indent if from the location header. Defaults to 4.
        """

        loc: Location = diagnostic.location
        if loc.lineno != loc.end_lineno:
            self.print_multiline(lines, diagnostic, indent)
            return

        start_offset: int = loc.col_offset
        end_offset: int = loc.end_col_offset or (start_offset + 1)

        line: str = lines[loc.lineno - 1]
        before: str = line[:start_offset]
        after: str = line[end_offset:]

        color: int = self.COLORS.get(diagnostic.type, Ansi.WHITE)

        subject: str = Ansi.FG(color) + line[start_offset:end_offset] + Ansi.RESET
        cursor: str = (
            " " * start_offset
            + Ansi.FG(color)
            + "~" * (end_offset - start_offset)
            + "> "
            + diagnostic.message
            + Ansi.RESET
        )

        indent_str: str = " " * indent
        print(diagnostic.location_str + ":")
        print(indent_str + before + subject + after)
        print(indent_str + cursor)
        print()

    def print_multiline(
        self, all_lines: list[str], diagnostic: Diagnostic, indent: int = 4
    ):
        loc: Location = diagnostic.location
        lines: list[str] = all_lines[loc.lineno - 1 : loc.end_lineno]

        start_offset: int = loc.col_offset
        end_offset: int = loc.end_col_offset or (start_offset + 1)

        indent_str: str = " " * indent
        color: int = self.COLORS.get(diagnostic.type, Ansi.WHITE)
        res: str = indent_str + lines[0][:start_offset]
        res += Ansi.FG(color) + lines[0][start_offset:]
        for line in lines[1:-1]:
            res += "\n" + indent_str + line
        res += "\n" + indent_str + lines[-1][:end_offset]
        res += Ansi.RESET + lines[-1][end_offset:]

        print(diagnostic.location_str + ":")
        print(res)
        print()
        print(Ansi.FG(color) + diagnostic.message + Ansi.RESET)
        print()
