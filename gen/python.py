# type: ignore
# ruff: disable[F821, F401]

###> Imports
import ast
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, Optional, TypeVar

from midas.ast.location import Location

###<


###> MidasType | Type annotations | node
class BaseType:
    base: str
    param: Optional[MidasType]


class ConstraintType:
    type: MidasType
    constraint: ast.expr


class FrameColumn:
    name: Optional[str]
    type: Optional[MidasType]


class FrameType:
    columns: list[FrameColumn]


###<


###> Stmt | Statements
class Function:
    name: str
    posonlyargs: list[Argument]
    args: list[Argument]
    kwonlyargs: list[Argument]
    returns: Optional[MidasType]

    @dataclass(frozen=True, kw_only=True)
    class Argument:
        location: Optional[Location] = None
        name: Optional[str]
        type: Optional[MidasType]


###<
