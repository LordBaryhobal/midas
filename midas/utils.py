from dataclasses import dataclass
from typing import Any, Callable, Optional

import midas.ast.python as p
from midas.checker.types import Type
from midas.generator.collector import AssertionCollector

AllowRepeat = Callable[[object], bool]


class UniversalJSONDumper:
    @classmethod
    def dump(
        cls,
        obj: Any,
        include_keys: Optional[list[str | tuple[str, str]]] = None,
        allow_repeat: Optional[AllowRepeat] = None,
    ) -> Any:
        if include_keys is None:
            include_keys = []
        return cls._dump(obj, include_keys, allow_repeat, [])

    @classmethod
    def _dump(
        cls,
        obj: Any,
        include_keys: list[str | tuple[str, str]],
        allow_repeat: Optional[AllowRepeat],
        visited: list[Any],
    ) -> Any:
        if obj in visited:
            return None
        match obj:
            case str() | int() | float() | None:
                return obj
            case list() | set() | tuple():
                return [
                    cls._dump(child, include_keys, allow_repeat, visited)
                    for child in obj
                ]
            case dict():
                return {
                    str(k): cls._dump(v, include_keys, allow_repeat, visited)
                    for k, v in obj.items()
                }
            case object():
                if allow_repeat is None or not allow_repeat(obj):
                    visited.append(obj)
                return {
                    "_type": obj.__class__.__name__,
                } | {
                    k: cls._dump(v, include_keys, allow_repeat, visited)
                    for k, v in obj.__dict__.items()
                    if not k.startswith("_")
                    or k in include_keys
                    or (obj.__class__.__name__, k) in include_keys
                }
            case _:
                raise ValueError(f"Unsupported value: {obj}")


@dataclass(frozen=True, kw_only=True)
class TypedAST:
    stmts: list[p.Stmt]
    judgements: list[tuple[p.Expr, Type]]
    evaluated_casts: list[p.CastExpr]
    assertions: AssertionCollector
