from typing import Any, Optional


class UniversalJSONDumper:
    @classmethod
    def dump(
        cls, obj: Any, include_keys: Optional[list[str | tuple[str, str]]] = None
    ) -> Any:
        if include_keys is None:
            include_keys = []
        return cls._dump(obj, include_keys, [])

    @classmethod
    def _dump(
        cls, obj: Any, include_keys: list[str | tuple[str, str]], visited: list[Any]
    ) -> Any:
        if obj in visited:
            return None
        match obj:
            case str() | int() | float() | None:
                return obj
            case list() | set() | tuple():
                return [cls._dump(child, include_keys, visited) for child in obj]
            case dict():
                return {
                    str(k): cls._dump(v, include_keys, visited) for k, v in obj.items()
                }
            case object():
                visited.append(obj)
                return {
                    "_type": obj.__class__.__name__,
                } | {
                    k: cls._dump(v, include_keys, visited)
                    for k, v in obj.__dict__.items()
                    if not k.startswith("_")
                    or k in include_keys
                    or (obj.__class__.__name__, k) in include_keys
                }
            case _:
                raise ValueError(f"Unsupported value: {obj}")
