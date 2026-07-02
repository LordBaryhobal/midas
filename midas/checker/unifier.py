import logging
from typing import Optional

from midas.checker.registry import TypesRegistry
from midas.checker.types import (
    AppliedType,
    ColumnType,
    DataFrameType,
    Function,
    GenericType,
    TopType,
    Type,
    TypeVar,
)


class UnificationError(Exception): ...


class Unifier:
    def __init__(self, types: TypesRegistry) -> None:
        self.types: TypesRegistry = types
        self.logger: logging.Logger = logging.getLogger("Unifier")

    def unify_call(
        self,
        type: GenericType,
        positional: list[Type],
        keywords: dict[str, Type],
    ) -> Optional[Type]:
        concrete_func: Function = Function(
            pos_args=[
                Function.Argument(
                    pos=i,
                    name=str(i),
                    type=arg,
                    required=True,
                )
                for i, arg in enumerate(positional)
            ],
            args=[],
            kw_args=[
                Function.Argument(
                    pos=len(positional) + i,
                    name=name,
                    type=arg,
                    required=True,
                )
                for i, (name, arg) in enumerate(keywords.items())
            ],
            returns=TopType(),  # TODO: use expected type
        )
        return self.unify_generic(type, concrete_func, match_return=False)

    def unify_generic(
        self,
        template: GenericType,
        concrete: Type,
        match_return: bool = True,
    ) -> Optional[Type]:
        substitutions: dict[str, Type]
        try:
            substitutions = self.match(template.body, concrete, match_return)
        except UnificationError:
            return None

        args: list[Type] = []
        for param in template.params:
            if param.name not in substitutions:
                return None
            args.append(substitutions[param.name])

        applied: Type = self.types.apply_generic(template, args)
        return applied

    def match(
        self,
        template: Type,
        concrete: Type,
        match_return: bool = True,
    ) -> dict[str, Type]:
        # TODO: if concrete is Generic, record bound TypeVar. Then when merging
        # substitutions, check that the constraint is respected
        match (template, concrete):
            case (TypeVar(name=name), _):
                return {name: concrete}

            case (
                AppliedType(name=template_name, args=template_args),
                AppliedType(name=concrete_name, args=concrete_args),
            ) if template_name == concrete_name and len(template_args) == len(
                concrete_args
            ):
                substitutions: dict[str, Type] = {}
                for template_arg, concrete_arg in zip(template_args, concrete_args):
                    new_substistutions: dict[str, Type] = self.match(
                        template_arg, concrete_arg
                    )
                    substitutions = self.merge(substitutions, new_substistutions)

                return substitutions

            case (
                DataFrameType(columns=template_columns),
                DataFrameType(columns=concrete_columns),
            ) if len(template_columns) == len(concrete_columns):
                substitutions: dict[str, Type] = {}
                for template_column, concrete_column in zip(
                    template_columns, concrete_columns
                ):
                    if template_column.index != concrete_column or (
                        template_column.name != concrete_column.name
                    ):
                        self.logger.debug(
                            f"Column mismatch: template={template_column}, concrete={concrete_column}"
                        )
                        raise UnificationError
                    new_substistutions: dict[str, Type] = self.match(
                        template_column.type, concrete_column.type
                    )
                    substitutions = self.merge(substitutions, new_substistutions)
                return substitutions

            case (ColumnType(type=template_column), ColumnType(type=concrete_column)):
                return self.match(template_column, concrete_column)

            case (Function(), Function()):
                mapped: list[tuple[Function.Argument, Function.Argument]] = (
                    self.map_params(template, concrete)
                )
                substitutions: dict[str, Type] = {}
                for template_arg, concrete_arg in mapped:
                    arg_subs: dict[str, Type] = self.match(
                        template_arg.type, concrete_arg.type
                    )
                    substitutions = self.merge(substitutions, arg_subs)

                if match_return:
                    return_subs: dict[str, Type] = self.match(
                        template.returns, concrete.returns
                    )
                    substitutions = self.merge(substitutions, return_subs)

                return substitutions

            case _:
                self.logger.debug(f"Can't match {concrete!r} with {template!r}")
                return {}

    def merge(self, subs1: dict[str, Type], subs2: dict[str, Type]) -> dict[str, Type]:
        merged: dict[str, Type] = subs1.copy()

        for k, v in subs2.items():
            if k in merged and merged[k] != v:
                self.logger.debug(
                    f"Substitution already defined for {k} with type {merged[k]}, got {v}"
                )
                raise UnificationError
            merged[k] = v
        return merged

    def map_params(
        self, func1: Function, func2: Function
    ) -> list[tuple[Function.Argument, Function.Argument]]:
        pos1: list[Function.Argument] = func1.pos_args
        mixed1: list[Function.Argument] = func1.args
        kw1: list[Function.Argument] = func1.kw_args

        pos2: list[Function.Argument] = func2.pos_args
        mixed2: list[Function.Argument] = func2.args
        kw2: list[Function.Argument] = func2.kw_args

        mapped: list[tuple[Function.Argument, Function.Argument]] = []

        by_pos2: dict[int, Function.Argument] = {arg.pos: arg for arg in pos2 + mixed2}
        by_name2: dict[str, Function.Argument] = {arg.name: arg for arg in mixed2 + kw2}

        for arg1 in pos1:
            if (arg2 := by_pos2.get(arg1.pos)) is not None:
                mapped.append((arg1, arg2))

        for arg1 in mixed1:
            # Match both positionally and by name, conflicts are caught
            # when merging substitutions
            if (arg2 := by_pos2.get(arg1.pos)) is not None:
                mapped.append((arg1, arg2))

            if (arg2 := by_name2.get(arg1.name)) is not None:
                mapped.append((arg1, arg2))

        for arg1 in kw1:
            if (arg2 := by_name2.get(arg1.name)) is not None:
                mapped.append((arg1, arg2))

        return mapped
