import logging
from dataclasses import dataclass
from typing import Optional

from midas.ast.midas import MemberKind
from midas.checker.builtins import BUILTIN_SUBTYPES
from midas.checker.types import (
    AliasType,
    AppliedType,
    BaseType,
    ComplexType,
    ConstraintType,
    ExtensionType,
    Function,
    GenericType,
    OverloadedFunction,
    Predicate,
    TopType,
    Type,
    TypeVar,
    UnknownType,
    Variance,
    substitute_typevars,
)


@dataclass
class Member:
    kind: MemberKind
    type: Type


class TypesRegistry:
    def __init__(self) -> None:
        self.logger: logging.Logger = logging.getLogger("TypesRegistry")
        self._types: dict[str, Type] = {}
        self._members: dict[str, dict[str, Member]] = {}
        self._predicates: dict[str, Predicate] = {}

    def get_type(self, name: str) -> Type:
        """Get a type from its name

        Args:
            name (str): the name of the type

        Raises:
            NameError: if the type is not defined

        Returns:
            Type: the type
        """
        if name in self._types:
            return self._types[name]
        raise NameError(f"Undefined type {name}")

    def define_type(self, name: str, type: Type) -> Type:
        """Define a type in the registry

        Args:
            name (str): the name of the type
            type (Type): the type to define

        Raises:
            ValueError: if a type is already defined with that name

        Returns:
            Type: the defined type
        """
        if name in self._types:
            raise ValueError(f"Type {name} already defined")
        self._types[name] = type
        return type

    def define_member(
        self,
        type_name: str,
        member_name: str,
        member_type: Type,
        kind: MemberKind,
    ):
        members: dict[str, Member] = self._members.setdefault(type_name, {})
        if member_name in members:
            current: Member = members[member_name]
            if current.kind != kind:
                self.logger.error(
                    f"Member '{member_name}' is already defined as a {current.kind},"
                    + f" cannot define a {kind} with the same name"
                )
                return
            if kind != MemberKind.METHOD:
                self.logger.error(
                    f"Member '{member_name}' already defined for type {type_name},"
                    + " only methods can be overloaded"
                )
                return

            combined: Type
            match current.type:
                case OverloadedFunction(overloads=overloads):
                    combined = OverloadedFunction(overloads=overloads + [member_type])
                case _:
                    combined = OverloadedFunction(overloads=[current.type, member_type])
            members[member_name] = Member(kind=current.kind, type=combined)

        else:
            members[member_name] = Member(kind=kind, type=member_type)

    def define_predicate(self, name: str, predicate: Predicate):
        if name in self._predicates:
            raise ValueError(f"Predicate {name} already defined")
        self._predicates[name] = predicate

    def is_subtype(self, type1: Type, type2: Type) -> bool:
        """Check whether `type1` is a subtype of `type2`

        For more details on the rules checked here, see TAPL Chap. 15-16-17

        Args:
            type1 (Type): the potential subtype
            type2 (Type): the potential supertype

        Returns:
            bool: whether `type1` is a subtype of `type2`
        """

        if type1 == type2:
            return True

        match (type1, type2):
            case (_, TopType()):
                return True

            case (_, UnknownType()):
                return True

            case (TypeVar(bound=bound), _):
                if bound is None:
                    return False
                return self.is_subtype(bound, type2)

            case (_, TypeVar(bound=bound)):
                if bound is None:
                    return True
                return self.is_subtype(type1, bound)

            case (AliasType(type=base1), _):
                return self.is_subtype(base1, type2)

            case (BaseType(name=name1), BaseType(name=name2)):
                return name1 in BUILTIN_SUBTYPES.get(name2, set())

            case (ComplexType(properties=props1), ComplexType(properties=props2)):
                for k, t in props2.items():
                    if k not in props1:
                        return False
                    if not self.is_subtype(props1[k], t):
                        return False
                return True

            case (Function(), Function()):
                return self.is_func_subtype(type1, type2)

            case (ConstraintType(type=base1), _):
                return self.is_subtype(base1, type2)

            case (
                AppliedType(name=name1, args=args1),
                AppliedType(name=name2, args=args2),
            ) if (
                name1 == name2
            ):
                generic: Type = self.get_type(name1)
                assert isinstance(generic, GenericType)
                for param, arg1, arg2 in zip(generic.params, args1, args2):
                    variance: Variance = param.variance
                    if variance in {Variance.INVARIANT, Variance.COVARIANT}:
                        if not self.is_subtype(arg1, arg2):
                            return False
                    if variance in {Variance.INVARIANT, Variance.CONTRAVARIANT}:
                        if not self.is_subtype(arg2, arg1):
                            return False
                return True

        return False

    # TODO: verify the logic in here
    def is_func_subtype(self, func1: Function, func2: Function) -> bool:
        """Check whether a function is a subtype of another

        Args:
            func1 (Function): the potential function subtype
            func2 (Function): the potential function supertype

        Returns:
            bool: whether `func1` is a subtype of `func2`
        """
        if not self.is_subtype(func1.returns, func2.returns):
            return False

        pos1: list[Function.Argument] = func1.pos_args
        mixed1: list[Function.Argument] = func1.args
        kw1: dict[str, Function.Argument] = {a.name: a for a in func1.kw_args}
        pos2: list[Function.Argument] = func2.pos_args
        mixed2: list[Function.Argument] = func2.args
        kw2: dict[str, Function.Argument] = {a.name: a for a in func2.kw_args}

        mixed_by_pos: dict[int, Function.Argument] = {arg.pos: arg for arg in mixed2}
        mixed_by_name: dict[str, Function.Argument] = {arg.name: arg for arg in mixed2}

        def is_arg_subtype(sub: Function.Argument, sup: Function.Argument) -> bool:
            if not self.is_subtype(sub.type, sup.type):
                return False
            if not sup.required and sub.required:
                return False
            return True

        for arg1 in pos1:
            arg2: Function.Argument
            if arg1.pos < len(pos2):
                arg2 = pos2[arg1.pos]
            elif arg1.pos in mixed_by_pos:
                arg2 = mixed_by_pos[arg1.pos]
            elif not arg1.required:
                continue
            else:
                return False
            if not is_arg_subtype(arg2, arg1):
                return False

        for name, arg1 in kw1.items():
            arg2: Function.Argument
            if name in kw2:
                arg2 = kw2[name]
            elif name in mixed_by_name:
                arg2 = mixed_by_name[name]
            elif not arg1.required:
                continue
            else:
                return False
            if not is_arg_subtype(arg2, arg1):
                return False

        for arg1 in mixed1:
            pos_arg2: Optional[Function.Argument] = None
            kw_arg2: Optional[Function.Argument] = None
            if arg1.name in kw2:
                kw_arg2 = kw2[arg1.name]
            elif arg1.name in mixed_by_name:
                kw_arg2 = mixed_by_name[arg1.name]
            if arg1.pos < len(pos2):
                pos_arg2 = pos2[arg1.pos]
            elif arg1.pos in mixed_by_pos:
                pos_arg2 = mixed_by_pos[arg1.pos]

            # No match in func2 and arg is required
            if pos_arg2 is None and kw_arg2 is None and arg1.required:
                return False

            # Matching keyword argument
            if kw_arg2 is not None and not is_arg_subtype(kw_arg2, arg1):
                return False

            # Matching positional argument
            if pos_arg2 is not None and not is_arg_subtype(pos_arg2, arg1):
                return False

        mixed_positions: set[int] = {a.pos for a in mixed1}
        mixed_names: set[str] = {a.name for a in mixed1}
        for arg2 in pos2:
            if not arg2.required:
                continue
            if arg2.pos >= len(pos1) and arg2.pos not in mixed_positions:
                return False

        for name, arg2 in kw2.items():
            if not arg2.required:
                continue
            if name not in kw1 and name not in mixed_names:
                return False

        for arg2 in mixed2:
            if arg2.required:
                continue
            pos_match: bool = arg2.pos < len(pos1) or arg2.pos in mixed_positions
            kw_match: bool = arg2.name in kw1 or arg2.name in mixed_names
            if not pos_match or not kw_match:
                return False

        return True

    def apply_generic(self, type: Type, args: list[Type]) -> Type:
        match type:
            case AliasType(name=name, type=base):
                return AliasType(name=name, type=self.apply_generic(base, args))

            case GenericType(name=name, params=type_vars, body=body):
                n_args: int = len(args)
                n_type_vars: int = len(type_vars)
                if n_args < n_type_vars:
                    raise ValueError(
                        f"Missing type arguments, expected {n_type_vars} but only {n_args} provided"
                    )
                if n_args > n_type_vars:
                    raise ValueError(
                        f"Too many type arguments, expected {n_type_vars} but {n_args} provided"
                    )
                substitutions: dict[str, Type] = {}
                for arg, type_var in zip(args, type_vars):
                    if type_var.bound is not None and not self.is_subtype(
                        arg, type_var.bound
                    ):
                        raise ValueError(
                            f"Type argument {arg} is not a subtype of {type_var.bound}"
                        )
                    substitutions[type_var.name] = arg
                return AppliedType(
                    name=name,
                    args=args,
                    body=substitute_typevars(body, substitutions),
                )

            case _:
                raise ValueError(f"{type} is not a generic type")

    def reduce_types(self, types: list[Type]) -> list[Type]:
        """Reduce a list of types to remove subtypes and only keep the highest types

        Args:
            types (list[Type]): the types to reduce

        Returns:
            list[Type]: the reduced list of types
        """

        reduced: bool = True
        keep: list[int] = list(range(len(types)))
        while reduced:
            reduced = False
            for i, i1 in enumerate(keep):
                type1: Type = types[i1]
                for i2 in keep[i + 1 :]:
                    type2 = types[i2]
                    if self.is_subtype(type1, type2):
                        keep.remove(i1)
                    elif self.is_subtype(type2, type1):
                        keep.remove(i2)
                    else:
                        continue
                    reduced = True
                    break
        return [types[i] for i in keep]

    def lookup_member(self, type: Type, member_name: str) -> Optional[Type]:
        match type:
            case BaseType(name=name):
                if name in self._members:
                    if member_name in self._members[name]:
                        return self._members[name][member_name].type
                return None

            case AliasType(name=name, type=base):
                if name in self._members:
                    if member_name in self._members[name]:
                        return self._members[name][member_name].type
                return self.lookup_member(base, member_name)

            case AppliedType(name=name, body=body, args=args):
                generic: Type = self.get_type(name)

                if not isinstance(generic, GenericType):
                    raise ValueError("AppliedType not derived from a GenericType")

                substitutions = {
                    type_var.name: arg for arg, type_var in zip(args, generic.params)
                }
                if name in self._members:
                    if member_name in self._members[name]:
                        member_type: Type = self._members[name][member_name].type
                        return substitute_typevars(member_type, substitutions)

                member_type2: Optional[Type] = self.lookup_member(body, member_name)
                if member_type2 is not None:
                    member_type2 = substitute_typevars(member_type2, substitutions)
                return member_type2

            case ComplexType(members=members):
                if member_name in members:
                    return members[member_name]
                self.logger.debug(f"No member '{member_name}' in {type}")
                return None

            case ExtensionType(base=base, extension=ComplexType(members=members)):
                if member_name in members:
                    return members[member_name]
                self.logger.debug(
                    f"No member '{member_name}' on {type}, looking up in base"
                )
                return self.lookup_member(base, member_name)

            case ConstraintType(type=base):
                return self.lookup_member(base, member_name)

            case UnknownType():
                return UnknownType()

            case _:
                self.logger.debug(f"Can't get member on {type}")
                return None

    def lookup_predicate(self, name: str) -> Optional[Predicate]:
        return self._predicates.get(name)
