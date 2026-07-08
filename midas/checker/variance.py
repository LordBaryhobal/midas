from __future__ import annotations

from typing import Literal, Optional, cast

from midas.checker.registry import Member, TypesRegistry
from midas.checker.types import (
    AppliedType,
    ConstraintType,
    Function,
    GenericType,
    OverloadedFunction,
    Type,
    TypeVar,
    Variance,
)

Polarity = Literal[-1, 0, 1]


class Tracker:
    """Helper class to track the polarity of type parameter references and computer their variance"""

    def __init__(self, vars: list[TypeVar]) -> None:
        self.vars: list[TypeVar] = vars
        self.refs: dict[str, set[Polarity]] = {var.name: set() for var in self.vars}

    def record(self, var: TypeVar, polarity: Polarity):
        """Record a polarity of the given type parameter

        Args:
            var (TypeVar): the type parameter
            polarity (Polarity): the polarity
        """
        self.refs[var.name].add(polarity)

    def get_updated_vars(self) -> list[TypeVar]:
        """Get a list of the tracked type variables with their recorded variance

        Returns:
            list[TypeVar]: the list of update type parameters
        """
        return [
            TypeVar(
                name=var.name, bound=var.bound, variance=self.get_variance(var.name)
            )
            for var in self.vars
        ]

    def get_variance(self, name: str) -> Variance:
        """Get the variance of a type parameter

        If the type parameter is only referenced in positive positions, it is
        covariant. If it is only referenced in negative positions, it is
        contravariant. Otherwise, it is invariant

        Args:
            name (str): the name of the type parameter

        Returns:
            Variance: the variance of the type parameter
        """
        refs: set[Polarity] = self.refs[name]
        if refs == {-1}:
            return Variance.CONTRAVARIANT
        if refs == {1}:
            return Variance.COVARIANT
        return Variance.INVARIANT

    def __contains__(self, item: TypeVar | str):
        if isinstance(item, TypeVar):
            return item.name in self
        return item in self.refs


class VarianceInferrer:
    """Helper class to compute type parameter variance"""

    def __init__(self, manager: VarianceManager) -> None:
        self.manager: VarianceManager = manager
        self.tracker: Tracker = Tracker([])

    @property
    def types(self) -> TypesRegistry:
        return self.manager.types

    def infer(self, type: GenericType) -> GenericType:
        """Infer the variance of a generic type's parameters

        Args:
            type (GenericType): the generic type

        Returns:
            GenericType: a new generic type with its parameters updated with
                their inferred variance
        """
        self.tracker = Tracker(type.params)

        self.walk(type.body, 1, type.name)
        members: dict[str, Member] = self.types._members.get(type.name, {})
        for name, member in members.items():
            self.walk(member.type, 1, type.name, [f"member:'{name}'"])

        return GenericType(
            name=type.name,
            params=self.tracker.get_updated_vars(),
            body=type.body,
        )

    def walk(
        self,
        type: Type,
        polarity: Polarity,
        base_name: str,
        path: Optional[list[str]] = None,
    ):
        """Walk the type nodes and record variance

        This function recurses into type substructures (e.g. function parameters,
        overloads, constraint type bases, etc.)

        When recursing, the polarity is flipped for consumer positions (e.g. function
        parameters) or kept the same for producer positions (e.g. return type)

        Args:
            type (Type): the type to visit
            polarity (Polarity): the current polarity
            base_name (str): the root generic type name (used to detect and
                handle cyclic references)
            path (Optional[list[str]], optional): the path to reach the current
                type from the root generic type (used for debugging). Defaults to None.
        """
        if path is None:
            path = []

        match type:
            # Arguments are negative positions -> flip polarity
            # Return is positive position -> keep polarity
            case Function(params=spec):
                all_params: list[Function.Parameter] = spec.pos + spec.mixed + spec.kw
                for param in all_params:
                    self.walk(
                        param.type,
                        -polarity,
                        base_name,
                        path + [f"param:'{param.name}'"],
                    )

                self.walk(type.returns, polarity, base_name, path + ["return"])

            # Walk all overloads
            case OverloadedFunction(overloads=overloads):
                for overload in overloads:
                    self.walk(overload, polarity, base_name, path)

            # If same name as root generic -> skip
            # Get inferred variance of parameters and multiply with current
            # polarity to recurse through arguments
            case AppliedType(name=name, args=args):
                if self.manager.is_in_queue(name):
                    return

                generic: Type = self.types.get_type(name)
                assert isinstance(generic, GenericType)
                generic = self.manager.infer(name, generic)

                params: list[TypeVar] = generic.params
                polarities: dict[Variance, Polarity] = {
                    Variance.INVARIANT: 0,
                    Variance.COVARIANT: 1,
                    Variance.CONTRAVARIANT: -1,
                }
                for arg, param in zip(args, params):
                    param_polarity: Polarity = polarities[param.variance]
                    self.walk(
                        arg,
                        cast(Polarity, polarity * param_polarity),
                        base_name,
                        path + [f"applied:'{name}'"],
                    )

            # Walk base type
            case ConstraintType(type=base):
                self.walk(base, polarity, base_name, path + ["constraint"])

            # Reached end
            # If tracked, record polarity
            case TypeVar():
                if type in self.tracker:
                    self.tracker.record(type, polarity)


class VarianceManager:
    """Coordinator for VarianceInferrer to handle recursive types"""

    def __init__(self, types: TypesRegistry) -> None:
        self.types: TypesRegistry = types
        self._queue: list[str] = []
        self._inferred: set[str] = set()

    def infer_all(self):
        """Infer variance on all generic types defined in the registry"""

        for name, type in self.types._types.items():
            if isinstance(type, GenericType):
                self.infer(name, type)

    def infer(self, name: str, type: GenericType) -> GenericType:
        """Infer variance of parameters of the given type

        Args:
            name (str): the type's name
            type (GenericType): the type

        Returns:
            GenericType: a new generic type with its parameters updated with
                their inferred variance
        """
        if self.is_inferred(name):
            return type

        self._queue.append(name)

        inferrer: VarianceInferrer = VarianceInferrer(self)
        inferred: GenericType = inferrer.infer(type)
        self.types._types[name] = inferred

        self._queue.pop()
        self._inferred.add(name)

        return inferred

    def is_in_queue(self, name: str) -> bool:
        """Whether the given type's variance is currently being inferred

        Args:
            name (str): the type's name

        Returns:
            bool: whether the type is in the queue
        """
        return name in self._queue

    def is_inferred(self, name: str) -> bool:
        """Whether the given type's variance has already been inferred

        Args:
            name (str): the type's name

        Returns:
            bool: whether the type has been processed
        """
        return name in self._inferred
