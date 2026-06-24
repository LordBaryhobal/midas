from __future__ import annotations

from typing import Optional

from midas.ast.location import Location
from midas.checker.diagnostic import Diagnostic, DiagnosticType


class Reporter:
    def __init__(self):
        self.diagnostics: list[Diagnostic] = []

    def report(
        self,
        path: Optional[str],
        type: DiagnosticType,
        location: Location,
        message: str,
    ):
        self.diagnostics.append(
            Diagnostic(
                file_path=path,
                location=location,
                type=type,
                message=message,
            )
        )

    def for_file(self, path: Optional[str]) -> FileReporter:
        return FileReporter(self, path)


class FileReporter:
    def __init__(self, base_reporter: Reporter, path: Optional[str]) -> None:
        self.base_reporter: Reporter = base_reporter
        self.path: Optional[str] = path

    def for_file(self, path: Optional[str]) -> FileReporter:
        return FileReporter(self.base_reporter, path)

    def report(self, type: DiagnosticType, location: Location, message: str):
        self.base_reporter.report(self.path, type, location, message)

    def error(self, location: Location, message: str):
        self.report(
            type=DiagnosticType.ERROR,
            location=location,
            message=message,
        )

    def warning(self, location: Location, message: str):
        self.report(
            type=DiagnosticType.WARNING,
            location=location,
            message=message,
        )

    def info(self, location: Location, message: str):
        self.report(
            type=DiagnosticType.INFO,
            location=location,
            message=message,
        )

    def debug(self, location: Location, message: str):
        self.report(
            type=DiagnosticType.DEBUG,
            location=location,
            message=message,
        )
