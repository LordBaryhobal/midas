from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Optional

from midas.ast.location import Location


class DiagnosticType(StrEnum):
    ERROR = "Error"
    WARNING = "Warning"
    INFO = "Info"


@dataclass(frozen=True)
class Diagnostic:
    file_path: Path
    location: Location
    type: DiagnosticType
    message: str

    @property
    def location_str(self) -> str:
        start_loc: str = f"L{self.location.lineno}:{self.location.col_offset+1}"
        end_loc: Optional[str] = ""
        if (
            self.location.end_lineno is not None
            and self.location.end_col_offset is not None
        ):
            end_loc = f"L{self.location.end_lineno}:{self.location.end_col_offset+1}"
        loc: str = (
            f"at {start_loc}" if end_loc is None else f"from {start_loc} to {end_loc}"
        )
        return f"{self.type} in {self.file_path} {loc}"

    def __str__(self) -> str:
        return f"{self.location_str}: {self.message}"
