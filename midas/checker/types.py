from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class BaseType:
    name: str


@dataclass(frozen=True, kw_only=True)
class SimpleType:
    base: BaseType


@dataclass(frozen=True, kw_only=True)
class Operation:
    left: Type
    operator: str
    right: Type
    result: Type


@dataclass(frozen=True, kw_only=True)
class UnknownType:
    pass


Type = BaseType | SimpleType | UnknownType
