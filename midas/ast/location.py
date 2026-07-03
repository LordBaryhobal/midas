from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


class HasLocation(Protocol):
    lineno: int
    col_offset: int
    end_lineno: Optional[int]
    end_col_offset: Optional[int]


@dataclass(frozen=True, kw_only=True)
class Location:
    """Information about the location of an AST node"""

    lineno: int
    col_offset: int
    end_lineno: Optional[int]
    end_col_offset: Optional[int]

    @staticmethod
    def from_ast(obj: HasLocation) -> Location:
        return Location(
            lineno=obj.lineno,
            col_offset=obj.col_offset,
            end_lineno=obj.end_lineno,
            end_col_offset=obj.end_col_offset,
        )

    @staticmethod
    def span(start: Location, end: Location) -> Location:
        """Create a new location spanning from one location to another

        Args:
            start (Location): the starting location
            end (Location): the end location

        Returns:
            Location: a new location spanning from the start of `start`
                to the end of `end`
        """
        return Location(
            lineno=start.lineno,
            col_offset=start.col_offset,
            end_lineno=end.lineno,
            end_col_offset=end.end_col_offset,
        )
