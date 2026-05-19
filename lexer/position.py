from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Position:
    """A simple structure to store the position of a token"""
    file: Optional[str]
    line: int
    column: int

    def __repr__(self):
        return f"{self.file or ''}L{self.line}:{self.column}"
