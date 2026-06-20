from typing import Literal, Optional, cast

from midas.checker.registry import TypesRegistry
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
    def __init__(self, vars: list[TypeVar]) -> None:
        self.vars: list[TypeVar] = vars
        self.refs: dict[str, set[Polarity]] = {var.name: set() for var in self.vars}

    def record(self, var: TypeVar, polarity: Polarity):
        self.refs[var.name].add(polarity)

    def get_updated_vars(self) -> list[TypeVar]:
        return [
            TypeVar(
                name=var.name, bound=var.bound, variance=self.get_variance(var.name)
            )
            for var in self.vars
        ]

    def get_variance(self, name: str) -> Variance:
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
    def __init__(self, types: TypesRegistry) -> None:
        self.types: TypesRegistry = types
        self.tracker: Tracker = Tracker([])

    def infer(self, type: GenericType) -> GenericType:
        self.tracker = Tracker(type.params)

        self.walk(type.body, 1, type.name)
        members: dict[str, Type] = self.types._members.get(type.name, {})
        for name, member in members.items():
            self.walk(member, 1, type.name, [f"member:'{name}'"])

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
        if path is None:
            path = []

        match type:
            # Arguments are negative positions -> flip polarity
            # Return is positive position -> keep polarity
            case Function(pos_args=pos_args, args=mixed_args, kw_args=kw_args):
                all_args: list[Function.Argument] = pos_args + mixed_args + kw_args
                for arg in all_args:
                    self.walk(
                        arg.type,
                        -polarity,
                        base_name,
                        path + [f"arg:'{arg.name}'"],
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
                # TODO: handle mutually recursive types
                if name == base_name:
                    return
                generic: Type = self.types.get_type(name)
                assert isinstance(generic, GenericType)
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
