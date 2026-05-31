from __future__ import annotations

from typing import Optional

from midas.checker.types import Type


class Environment:
    """
    A scoped environment in which variables are defined

    Each environment can inherit from a parent/enclosing environment.
    """

    def __init__(self, enclosing: Optional[Environment] = None) -> None:
        self.enclosing: Optional[Environment] = enclosing
        self.values: dict[str, Type] = {}
        self.return_types: list[Type] = []

        self._children: list[Environment] = []
        if enclosing is not None:
            enclosing._children.append(self)

    def define(self, name: str, value: Type) -> None:
        """Define a variable in this environment

        Args:
            name (str): the name of the variable
            value (Type): the value
        """
        self.values[name] = value

    def get(self, name: str) -> Optional[Type]:
        """Get a variable in the closest environment which has a definition for it

        Args:
            name (str): the name of the variable

        Returns:
            Optional[Type]: the value of the variable, or None if it was not found
        """
        if name in self.values:
            return self.values[name]
        if self.enclosing is not None:
            return self.enclosing.get(name)
        # raise NameError(f"Undefined variable '{name}'")
        return None

    def assign(self, name: str, value: Type) -> bool:
        """Assign a new value to a variable in the environment it was defined in

        Args:
            name (str): the name of the variable
            value (Type): the new value

        Returns:
            bool: True if the variable was assigned in this environment or an ancestor, False otherwise
        """
        if name not in self.values:
            if self.enclosing is None:
                return False
            if self.enclosing.assign(name, value):
                return True
        self.values[name] = value
        return True

    def clear(self):
        """Clear all definitions in this environment"""
        self.values = {}

    def get_at(self, distance: int, name: str) -> Optional[Type]:
        """Get the value of a variable at a given distance

        A distance of 0 looks up in this environment, 1 in the parent environment, etc.
        This methods expects `distance` to be valid. An error will be raised if
        the stack does not extend far enough to reach `distance`

        Args:
            distance (int): the scope distance
            name (str): the name of the variable

        Returns:
            Optional[Type]: the value at the given distance, or None if it is not defined in that environment

        Raises:
            AssertionError: if the stack does not extend far enough to reach `distance`
        """
        return self.ancestor(distance).values.get(name)

    def assign_at(self, distance: int, name: str, value: Type) -> None:
        """Assign a new value to a variable at a given distance

        A distance of 0 assigns in this environment, 1 in the parent environment, etc.

        Args:
            distance (int): the scope distance
            name (str): the name of the variable
            value (Type): the new value

        Raises:
            AssertionError: if the stack does not extend far enough to reach `distance`
        """
        self.ancestor(distance).values[name] = value

    def ancestor(self, distance: int) -> Environment:
        """Get the ancestor at a given distance

        A distance of 0 references this environment, 1 the parent environment, etc.

        Args:
            distance (int): the scope distance

        Returns:
            Environment: the environment

        Raises:
            AssertionError: if the stack does not extend far enough to reach `distance`
        """
        env: Environment = self
        for _ in range(distance):
            assert env.enclosing is not None
            env = env.enclosing
        return env

    def flat_dict(self) -> dict[str, Type]:
        """Get the current environment including definitions in its ancestor as a flat dictionary

        This method recursively combines this environment definitions with its ancestor's

        Returns:
            dict: the combined environment
        """
        if self.enclosing is None:
            return self.values
        return self.enclosing.flat_dict() | self.values

    def dump(self) -> dict:
        return {
            "values": self.values,
            "return_types": self.return_types,
            "children": [child.dump() for child in self._children],
        }
