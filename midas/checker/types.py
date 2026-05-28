from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class BaseType:
    name: str


@dataclass(frozen=True, kw_only=True)
class SimpleType:
    name: str
    base: BaseType | SimpleType


@dataclass(frozen=True, kw_only=True)
class UnknownType:
    pass


Type = BaseType | SimpleType | UnknownType
