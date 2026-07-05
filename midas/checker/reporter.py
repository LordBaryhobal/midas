from __future__ import annotations

from typing import Optional

from midas.ast.location import Location
from midas.checker.diagnostic import Diagnostic, DiagnosticType


class Reporter:
    """Helper class to store diagnostics"""

    def __init__(self):
        self.diagnostics: list[Diagnostic] = []

    def report(
        self,
        path: Optional[str],
        type: DiagnosticType,
        location: Location,
        message: str,
    ):
        """Create and record a diagnostic

        Args:
            path (Optional[str]): the path linked to this diagnostic
            type (DiagnosticType): the type of diagnostic
            location (Location): the location if the diagnostic in the file
            message (str): the diagnostic's message
        """
        self.diagnostics.append(
            Diagnostic(
                file_path=path,
                location=location,
                type=type,
                message=message,
            )
        )

    def for_file(self, path: Optional[str]) -> FileReporter:
        """Create a new file reporter for the given path using this reporter

        Args:
            path (Optional[str]): the path for the new file reporter

        Returns:
            FileReporter: the new file reporter, linked to this reporter
        """
        return FileReporter(self, path)


class FileReporter:
    """Helper class to manage diagnostics for a file"""

    def __init__(self, base_reporter: Reporter, path: Optional[str]) -> None:
        self.base_reporter: Reporter = base_reporter
        self.path: Optional[str] = path

    def for_file(self, path: Optional[str]) -> FileReporter:
        """Create a new file reporter for the given path with the same base reporter

        Args:
            path (Optional[str]): the path for the new file reporter

        Returns:
            FileReporter: the file reporter
        """
        return FileReporter(self.base_reporter, path)

    def report(self, type: DiagnosticType, location: Location, message: str):
        """Report a diagnostic to the base reporter

        Args:
            type (DiagnosticType): the type of diagnostic
            location (Location): the location of the diagnostic in the file
            message (str): the diagnostic's message
        """
        self.base_reporter.report(self.path, type, location, message)

    def error(self, location: Location, message: str):
        """Report an error diagnostic

        Args:
            location (Location): the location of the diagnostic in the file
            message (str): the diagnostic's message
        """
        self.report(
            type=DiagnosticType.ERROR,
            location=location,
            message=message,
        )

    def warning(self, location: Location, message: str):
        """Report a warning diagnostic

        Args:
            location (Location): the location of the diagnostic in the file
            message (str): the diagnostic's message
        """
        self.report(
            type=DiagnosticType.WARNING,
            location=location,
            message=message,
        )

    def info(self, location: Location, message: str):
        """Report an info diagnostic

        Args:
            location (Location): the location of the diagnostic in the file
            message (str): the diagnostic's message
        """
        self.report(
            type=DiagnosticType.INFO,
            location=location,
            message=message,
        )

    def debug(self, location: Location, message: str):
        """Report a debug diagnostic

        Args:
            location (Location): the location of the diagnostic in the file
            message (str): the diagnostic's message
        """
        self.report(
            type=DiagnosticType.DEBUG,
            location=location,
            message=message,
        )
