from dataclasses import dataclass
from enum import StrEnum
from typing import Optional

from midas.ast.location import Location


class DiagnosticType(StrEnum):
    ERROR = "Error"
    WARNING = "Warning"
    INFO = "Info"
    DEBUG = "Debug"


@dataclass(frozen=True)
class Diagnostic:
    """Information about a diagnostic (warning, errors, etc.)

    Holds a location, a diagnostic type and a message.
    Optionally bound to a file path

    Returns:
        _type_: _description_
    """

    file_path: Optional[str]
    location: Location
    type: DiagnosticType
    message: str

    @property
    def location_str(self) -> str:
        """The diagnostic type and location as a human readable string

        The location is formatted as "<Type> in <file> from L<start_line>:<start_col> to <end_line>:<end_col>",
        for example: "Error in /home/user/Desktop/script.py from L12:5 to L12:8"

        If the file is `None`, the "in ..." section is excluded from the result.<br>
        If the location's end is not specified, the formulation "at L<start_line>:<start_col>" is used.

        Returns:
            str: _description_
        """

        start_loc: str = f"L{self.location.lineno}:{self.location.col_offset+1}"
        end_loc: Optional[str] = ""
        if (
            self.location.end_lineno is not None
            and self.location.end_col_offset is not None
        ):
            end_loc = f"L{self.location.end_lineno}:{self.location.end_col_offset+1}"

        loc: str = ""
        if self.file_path is not None:
            loc += f" in {self.file_path}"
        if end_loc is None:
            loc += f" at {start_loc}"
        else:
            loc += f" from {start_loc} to {end_loc}"

        return f"{self.type}{loc}"

    def __str__(self) -> str:
        return f"{self.location_str}: {self.message}"
