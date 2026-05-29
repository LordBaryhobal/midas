from __future__ import annotations

from typing import Optional

from midas.checker.types import Type


class Environment:
    def __init__(self, enclosing: Optional[Environment] = None) -> None:
        self.enclosing: Optional[Environment] = enclosing
        self.values: dict[str, Type] = {}
        self.return_types: set[Type] = set()

    def define(self, name: str, value: Type):
        self.values[name] = value

    def get(self, name: str) -> Optional[Type]:
        if name in self.values:
            return self.values[name]
        if self.enclosing is not None:
            return self.enclosing.get(name)
        # raise NameError(f"Undefined variable '{name}'")
        return None

    def assign(self, name: str, value: Type) -> bool:
        if name not in self.values:
            if self.enclosing is None:
                return False
            if self.enclosing.assign(name, value):
                return True
        self.values[name] = value
        return True

    def clear(self):
        self.values = {}

    def get_at(self, distance: int, name: str) -> Optional[Type]:
        return self.ancestor(distance).values.get(name)

    def assign_at(self, distance: int, name: str, value: Type):
        self.ancestor(distance).values[name] = value

    def ancestor(self, distance: int) -> Environment:
        env: Environment = self
        for _ in range(distance):
            assert env.enclosing is not None
            env = env.enclosing
        return env

    def flat_dict(self) -> dict:
        if self.enclosing is None:
            return self.values
        return self.enclosing.flat_dict() | self.values
