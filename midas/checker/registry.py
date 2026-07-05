import logging
from dataclasses import dataclass
from typing import Optional

from midas.ast.midas import MemberKind
from midas.checker.builtins import BUILTIN_SUBTYPES
from midas.checker.types import (
    AppliedType,
    BaseType,
    ColumnType,
    ComplexType,
    ConstraintType,
    DataFrameType,
    DerivedType,
    ExtensionType,
    Function,
    GenericType,
    OverloadedFunction,
    Predicate,
    TopType,
    TupleType,
    Type,
    TypeVar,
    UnknownType,
    Variance,
    substitute_typevars,
)


@dataclass
class Member:
    """A member of a type (property or method)"""

    kind: MemberKind
    type: Type


class TypesRegistry:
    """A registry of types, type members and predicates"""

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
        """Define a member on a type

        If the member is a method and a member with the same name is already
        defined on the given type, the two are combined into an :class:`OverloadedFunction`.

        If the member is a property and a member with the same name is already
        defined on the given type, the new definition is dropped and an error
        is reported.

        In any case, if a member with the same name but a different kind is
        already defined on the given type, the new definition is dropped and
        an error is reported.

        Args:
            type_name (str): the name of the type on which the member is defined
            member_name (str): the name of the new member
            member_type (Type): the type of the new member
            kind (MemberKind): the kind of member to define (property or method)
        """
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
        """Define a predicate

        Args:
            name (str): the name of the new predicate
            predicate (Predicate): the predicate to define

        Raises:
            ValueError: if a predicate with the same name is already defined
        """
        if name in self._predicates:
            raise ValueError(f"Predicate {name} already defined")
        self._predicates[name] = predicate

    def is_builtin_subtype(self, name1: str, name2: str) -> bool:
        """Check whether a type is a subtype of another base on builtin subtype rules

        Args:
            name1 (str): the name of the potential subtype
            name2 (str): the name of the potential supertype

        Returns:
            bool: _description_
        """
        subtypes: set[str] = BUILTIN_SUBTYPES.get(name2, set())
        if name1 in subtypes:
            return True
        for subtype in subtypes:
            if self.is_builtin_subtype(name1, subtype):
                return True
        return False

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

            case (DerivedType(type=base1), _):
                return self.is_subtype(base1, type2)

            case (BaseType(name=name1), BaseType(name=name2)):
                return self.is_builtin_subtype(name1, name2)

            case (ComplexType(properties=props1), ComplexType(properties=props2)):
                for k, t in props2.items():
                    if k not in props1:
                        return False
                    if not self.is_subtype(props1[k], t):
                        return False
                return True

            case (DataFrameType(columns=columns1), DataFrameType(columns=columns2)):
                # TODO: check order?
                by_name1: dict[str, DataFrameType.Column] = {
                    col.name: col for col in columns1 if col.name is not None
                }
                for col2 in columns2:
                    if col2.name not in by_name1:
                        return False
                    if not self.is_subtype(by_name1[col2.name].type, col2.type):
                        return False
                return True

            case (ColumnType(type=inner1), ColumnType(type=inner2)):
                # TODO: invariant, replace ColumnType with simple GenericType
                if not self.are_equivalent(inner1, inner2):
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

            # TODO: verify legitimacy
            case (AppliedType(body=body), _):
                return self.is_subtype(body, type2)

        return False

    def are_equivalent(self, type1: Type, type2: Type) -> bool:
        """Check whether two types are equivalent (T <: S and S <: T)

        Args:
            type1 (Type): the first type
            type2 (Type): the second type

        Returns:
            bool: whether `type1` is a subtype and a supertype of `type2`
        """
        return self.is_subtype(type1, type2) and self.is_subtype(type2, type1)

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

        pos1: list[Function.Parameter] = func1.params.pos
        mixed1: list[Function.Parameter] = func1.params.mixed
        kw1: dict[str, Function.Parameter] = {
            param.name: param for param in func1.params.kw
        }
        pos2: list[Function.Parameter] = func2.params.pos
        mixed2: list[Function.Parameter] = func2.params.mixed
        kw2: dict[str, Function.Parameter] = {
            param.name: param for param in func2.params.kw
        }

        mixed_by_pos: dict[int, Function.Parameter] = {
            param.pos: param for param in mixed2
        }
        mixed_by_name: dict[str, Function.Parameter] = {
            param.name: param for param in mixed2
        }

        def is_arg_subtype(sub: Function.Parameter, sup: Function.Parameter) -> bool:
            if not self.is_subtype(sub.type, sup.type):
                return False
            if not sup.required and sub.required:
                return False
            return True

        for param1 in pos1:
            param2: Function.Parameter
            if param1.pos < len(pos2):
                param2 = pos2[param1.pos]
            elif param1.pos in mixed_by_pos:
                param2 = mixed_by_pos[param1.pos]
            elif not param1.required:
                continue
            else:
                return False
            if not is_arg_subtype(param2, param1):
                return False

        for name, param1 in kw1.items():
            param2: Function.Parameter
            if name in kw2:
                param2 = kw2[name]
            elif name in mixed_by_name:
                param2 = mixed_by_name[name]
            elif not param1.required:
                continue
            else:
                return False
            if not is_arg_subtype(param2, param1):
                return False

        for param1 in mixed1:
            pos_param2: Optional[Function.Parameter] = None
            kw_param2: Optional[Function.Parameter] = None
            if param1.name in kw2:
                kw_param2 = kw2[param1.name]
            elif param1.name in mixed_by_name:
                kw_param2 = mixed_by_name[param1.name]
            if param1.pos < len(pos2):
                pos_param2 = pos2[param1.pos]
            elif param1.pos in mixed_by_pos:
                pos_param2 = mixed_by_pos[param1.pos]

            # No match in func2 and arg is required
            if pos_param2 is None and kw_param2 is None and param1.required:
                return False

            # Matching keyword argument
            if kw_param2 is not None and not is_arg_subtype(kw_param2, param1):
                return False

            # Matching positional argument
            if pos_param2 is not None and not is_arg_subtype(pos_param2, param1):
                return False

        mixed_positions: set[int] = {param.pos for param in mixed1}
        mixed_names: set[str] = {param.name for param in mixed1}
        for param2 in pos2:
            if not param2.required:
                continue
            if param2.pos >= len(pos1) and param2.pos not in mixed_positions:
                return False

        for name, param2 in kw2.items():
            if not param2.required:
                continue
            if name not in kw1 and name not in mixed_names:
                return False

        for param2 in mixed2:
            if param2.required:
                continue
            pos_match: bool = param2.pos < len(pos1) or param2.pos in mixed_positions
            kw_match: bool = param2.name in kw1 or param2.name in mixed_names
            if not pos_match or not kw_match:
                return False

        return True

    def apply_generic(self, type: Type, args: list[Type]) -> Type:
        """Instantiate a generic type with the given type arguments

        Args:
            type (Type): the generic
            args (list[Type]): the type arguments

        Raises:
            ValueError: if the arguments are invalid (wrong number, bound violation)

        Returns:
            Type: the applied generic type
        """
        match type:
            case DerivedType(name=name, type=base):
                return DerivedType(name=name, type=self.apply_generic(base, args))

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

            case BaseType(name="tuple"):
                return TupleType(items=tuple(args))

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
        """Lookup a member by name on a given type

        This function first looks up directly on the specified type, then
        recurse through supertypes until it finds the member or reaches
        the root type

        Args:
            type (Type): the type on which to lookup the member
            member_name (str): the member's name

        Returns:
            Optional[Type]: the member's type, or `None` if it is not defined
        """
        match type:
            case BaseType(name=name):
                if name in self._members:
                    if member_name in self._members[name]:
                        return self._members[name][member_name].type
                return None

            case DerivedType(name=name, type=base):
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

            case TypeVar(bound=bound) if bound is not None:
                return self.lookup_member(bound, member_name)

            case UnknownType():
                return UnknownType()

            case _:
                self.logger.debug(f"Can't get member on {type}")
                return None

    def lookup_predicate(self, name: str) -> Optional[Predicate]:
        """Lookup a predicate by name

        Args:
            name (str): the name of the predicate

        Returns:
            Optional[Predicate]: the predicate, or `None` if is not defined
        """
        return self._predicates.get(name)

    def _by_name_or_type(self, name_or_type: str | Type) -> Type:
        """Get a type by name or return it as is

        If `name_or_type` is a string, the associated type is looked up and returned.
        Otherwise, the type is returned as is.

        Args:
            name_or_type (str | Type): the type or type's name

        Returns:
            Type: the type
        """
        if isinstance(name_or_type, str):
            return self.get_type(name_or_type)
        return name_or_type

    def list_of(self, item_type: str | Type) -> Type:
        """Helper method to type a list of a given item type

        Args:
            item_type (str | Type): the item type

        Returns:
            Type: the list type
        """
        list_ = self.get_type("list")
        return self.apply_generic(list_, [self._by_name_or_type(item_type)])

    def tuple_of(self, *item_types: str | Type) -> Type:
        """Helper method to type a tuple of given item types

        Args:
            item_type (str | Type): the item types

        Returns:
            Type: the tuple type
        """

        tuple_ = self.get_type("tuple")
        return self.apply_generic(
            tuple_,
            [self._by_name_or_type(item_type) for item_type in item_types],
        )

    def dict_of(self, key_type: str | Type, value_type: str | Type) -> Type:
        """Helper method to type a dict of given key and value types

        Args:
            key_type (str | Type): the key type
            value_type (str | Type): the value type

        Returns:
            Type: the dict type
        """
        dict_ = self.get_type("dict")
        return self.apply_generic(
            dict_,
            [
                self._by_name_or_type(key_type),
                self._by_name_or_type(value_type),
            ],
        )
