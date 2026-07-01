import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, Optional, Protocol, TypeVar, Union

from midas.ast.location import Location
from midas.checker.registry import TypesRegistry
from midas.checker.reporter import FileReporter
from midas.checker.types import (
    AppliedType,
    DerivedType,
    Function,
    GenericType,
    OverloadedFunction,
    Type,
    UnknownType,
    unfold_type,
)
from midas.checker.unifier import Unifier


class HasLocation(Protocol):
    @property
    def location(self) -> Location: ...


E = TypeVar("E", bound=HasLocation)

TypedExpr = tuple[E, Type]


@dataclass(frozen=True, kw_only=True)
class MappedArgument(Generic[E]):
    expr: E
    type: Type
    argument: Function.Argument


@dataclass(frozen=True, kw_only=True)
class OverloadCandidate:
    function: Function
    mapped: list[MappedArgument]


class CallError(StrEnum):
    INVALID_ARGS = "Invalid arguments"
    NO_MATCHING_OVERLOAD = "No matching overload"
    IMPOSSIBLE_UNIFICATION = "Parameters unification failed"
    NOT_CALLABLE = "Not callable"


@dataclass(frozen=True, kw_only=True)
class CallResult:
    error: Optional[CallError] = None
    result: Type = UnknownType()
    message: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return self.error is None

    @property
    def error_message(self) -> str:
        if self.message is not None:
            return self.message
        if self.error is not None:
            return str(self.error)
        return ""


class CallDispatcher(Generic[E]):
    def __init__(self, types: TypesRegistry, reporter: FileReporter) -> None:
        self.types: TypesRegistry = types
        self.reporter: FileReporter = reporter
        self.logger: logging.Logger = logging.getLogger("CallDispatcher")

    def get_result(
        self,
        location: Location,
        callee: Type,
        positional: list[TypedExpr[E]],
        keywords: dict[str, TypedExpr[E]],
        report_errors: bool = True,
    ) -> CallResult:
        """Get the result type of a function call

        If the function has overloads, the function will try to resolve the
        appropriate signature.
        Argument types are matched to the defined parameters.
        The function doesn't take the raw expression as a parameter to accommodate
        for desugared calls such as for operators.

        Args:
            location (Location): the call location
            callee (Type): the called function
            positional (list[TypedExpr]): the list positional arguments
            keywords (dict[str, TypedExpr]): the map of keyword arguments
            report_errors (bool, optional): whether type errors should be reported as diagnostics. Defaults to True.

        Returns:
            Type: the return type of the call, or `None` if either
            the call is invalid or no overload matched the arguments uniquely
        """
        match callee:
            case Function() as function:
                valid: bool
                mapped: list[MappedArgument[E]]
                valid, mapped = self.map_call_arguments(
                    function, location, positional, keywords
                )
                valid = valid and self._are_arguments_valid(mapped, report_errors)
                if not valid:
                    return CallResult(error=CallError.INVALID_ARGS)
                return CallResult(result=function.returns)

            case OverloadedFunction(overloads=overloads):
                res = self._match_overload(
                    overloads, location, positional, keywords, report_errors
                )
                if res[0] is None:
                    return CallResult(
                        error=CallError.NO_MATCHING_OVERLOAD,
                        message=res[1],
                    )
                return CallResult(result=res[0].returns)

            case AppliedType(body=body):
                return self.get_result(
                    location, body, positional, keywords, report_errors
                )

            case UnknownType():
                return CallResult(result=UnknownType())

            case DerivedType(type=base):
                return self.get_result(
                    location, base, positional, keywords, report_errors
                )

            case GenericType():
                unifier: Unifier = Unifier(self.types)
                pos: list[Type] = [a[1] for a in positional]
                kw: dict[str, Type] = {k: v[1] for k, v in keywords.items()}
                unified: Optional[Type] = unifier.unify_call(callee, pos, kw)
                if unified is None:
                    pos_str: str = ", ".join(str(t) for t in pos)
                    kw_str: str = ", ".join(f"{k}: {v}" for k, v in kw.items())
                    message: str = (
                        f"Could not unify {callee}={callee.body} with pos=[{pos_str}] and kw={{{kw_str}}}"
                    )
                    if report_errors:
                        self.reporter.error(location, message)
                    return CallResult(
                        error=CallError.IMPOSSIBLE_UNIFICATION,
                        message=message,
                    )
                return self.get_result(
                    location,
                    unified,
                    positional,
                    keywords,
                    report_errors,
                )

            case _:
                message: str = f"{callee} ({callee.__class__.__name__}) is not callable"
                if report_errors:
                    self.reporter.error(location, message)
                return CallResult(
                    error=CallError.NOT_CALLABLE,
                    message=message,
                )

    def _are_arguments_valid(
        self,
        arguments: list[MappedArgument[E]],
        report_errors: bool = True,
    ) -> bool:
        """Check whether the passed argument types correspond to their matched parameter definitions

        Args:
            arguments (list[MappedArgument]): the list of argument/parameter pairs
            report_errors (bool, optional): whether type errors should be reported as diagnostics. Defaults to True.

        Returns:
            bool: True if all arguments fit the matching parameter definitions, False otherwise
        """
        valid: bool = True
        for arg in arguments:
            if not self.types.is_subtype(arg.type, arg.argument.type):
                if report_errors:
                    self.reporter.error(
                        arg.expr.location,
                        f"Wrong type for argument '{arg.argument.name}', expected {arg.argument.type}, got {arg.type}",
                    )
                valid = False
        return valid

    def _match_overload(
        self,
        overloads: list[Type],
        location: Location,
        positional: list[TypedExpr[E]],
        keywords: dict[str, TypedExpr[E]],
        report_errors: bool = True,
    ) -> Union[tuple[Function, None], tuple[None, str]]:
        """Try and resolve the appropriate overload for the given arguments

        Args:
            overloads (list[Type]): the list of possible overloads
            location (Location): the call location
            positional (list[TypedExpr]): the list of positional arguments
            keywords (dict[str, TypedExpr]): the map of keywords arguments
            report_errors (bool, optional): whether type errors should be reported as diagnostics. Defaults to True.

        Returns:
            Optional[Function]: the resolved function signature if it can be
            determined unambiguously, or `None`.
        """
        candidates: list[OverloadCandidate] = []
        for overload in overloads:
            function: Type = unfold_type(overload)
            if not isinstance(function, Function):
                if report_errors:
                    self.logger.error(
                        f"Overload is not a function: {overload} is {function}"
                    )
                continue
            valid, mapped = self.map_call_arguments(
                function=function,
                location=location,
                positional=positional,
                keywords=keywords,
                report_errors=False,
            )
            if valid and self._are_arguments_valid(mapped, report_errors=False):
                candidates.append(
                    OverloadCandidate(
                        function=function,
                        mapped=mapped,
                    )
                )

        pos_types: str = ", ".join(str(type) for _, type in positional)
        kw_types: str = ", ".join(
            f"{name}: {type}" for name, (_, type) in keywords.items()
        )
        for_args: str = f"for arguments pos=[{pos_types}] and kw={{{kw_types}}}"

        n_candidates: int = len(candidates)

        # Exactly 1 match -> return it
        if n_candidates == 1:
            return candidates[0].function, None

        # No match -> invalid call
        if n_candidates == 0:
            overloads_str: str = ", ".join(map(str, overloads))
            message: str = f"No matching overload in [{overloads_str}] {for_args}"
            if report_errors:
                self.reporter.error(location, message)
            return None, message

        # Multiple matches -> see if one <: all others (more specific)
        for i1, c1 in enumerate(candidates):
            mapped1: list[MappedArgument[E]] = c1.mapped
            best_match: bool = True
            for i2, c2 in enumerate(candidates):
                if i1 == i2:
                    continue
                mapped2: list[MappedArgument[E]] = c2.mapped
                if not self._are_mapped_subtypes(mapped1, mapped2):
                    best_match = False
                    break
                self.logger.debug(f"{c1.function} is a full overload of {c2.function}")
            if best_match:
                return c1.function, None

        candidates_str: str = ", ".join(
            str(candidate.function) for candidate in candidates
        )
        message: str = f"Multiple matching overloads {for_args}: {candidates_str}"
        if report_errors:
            self.reporter.error(location, message)
        return None, message

    def map_call_arguments(
        self,
        function: Function,
        location: Location,
        positional: list[TypedExpr[E]],
        keywords: dict[str, TypedExpr[E]],
        report_errors: bool = True,
    ) -> tuple[bool, list[MappedArgument]]:
        """Map call arguments to a function's parameters as defined in its signature

        This method maps positional-only, keyword-only and mixed parameter definitions
        with the arguments passed at the call site

        Any mismatched, missing or unexpected argument is reported as a diagnostic,
        unless `report_errors` is set to `False`

        Args:
            function (Function): the function definition
            location (Location): the call location
            positional (list[TypedExpr]): the list of positional arguments
            keywords (dict[str, TypedExpr]): the map of keyword arguments
            report_errors (bool, optional): whether type errors should be reported as diagnostics. Defaults to True.

        Returns:
            tuple[bool, list[MappedArgument]]: a boolean reporting whether
            the call is valid and the list of mapped arguments
        """
        set_args: set[str] = set()

        required_positional: list[str] = [
            arg.name for arg in function.pos_args + function.args if arg.required
        ]
        required_keyword: list[str] = [
            arg.name for arg in function.kw_args if arg.required
        ]

        mapped: list[MappedArgument[E]] = []

        pos_params: list[Function.Argument] = list(function.pos_args)
        mixed_params: list[Function.Argument] = list(function.args)
        kw_params: dict[str, Function.Argument] = {
            arg.name: arg for arg in function.kw_args
        }

        valid_call: bool = True

        # TODO: handle *args and **kwargs sinks
        for arg in positional:
            param: Function.Argument
            if len(pos_params) != 0:
                param = pos_params.pop(0)
            elif len(mixed_params) != 0:
                param = mixed_params.pop(0)
            else:
                if report_errors:
                    self.reporter.error(
                        arg[0].location, "Too many positional arguments"
                    )
                valid_call = False
                break
            name: str = param.name
            if name in required_positional:
                required_positional.remove(name)
            if name in required_keyword:
                required_keyword.remove(name)
            set_args.add(name)
            mapped.append(
                MappedArgument(
                    expr=arg[0],
                    type=arg[1],
                    argument=param,
                )
            )

        kw_params.update({arg.name: arg for arg in mixed_params})
        for name, arg in keywords.items():
            param: Function.Argument
            if name not in kw_params:
                if report_errors:
                    if name in set_args:
                        self.reporter.error(
                            arg[0].location, f"Multiple values for argument '{name}'"
                        )
                    else:
                        self.reporter.error(
                            arg[0].location, f"Unknown keyword argument '{name}'"
                        )
                valid_call = False
                continue
            param = kw_params.pop(name)
            if name in required_positional:
                required_positional.remove(name)
            if name in required_keyword:
                required_keyword.remove(name)
            set_args.add(name)
            mapped.append(
                MappedArgument(
                    expr=arg[0],
                    type=arg[1],
                    argument=param,
                )
            )

        def join_args(args: list[str]) -> str:
            args = list(map(lambda a: f"'{a}'", args))
            if len(args) == 0:
                return ""
            if len(args) == 1:
                return args[0]
            return ", ".join(args[:-1]) + " and " + args[-1]

        if len(required_positional) != 0:
            plural: str = "" if len(required_positional) == 1 else "s"
            args: str = join_args(required_positional)
            if report_errors:
                self.reporter.error(
                    location,
                    f"Missing required positional argument{plural}: {args}",
                )
            valid_call = False

        if len(required_keyword) != 0:
            plural: str = "" if len(required_keyword) == 1 else "s"
            args: str = join_args(required_keyword)
            if report_errors:
                self.reporter.error(
                    location,
                    f"Missing required keyword argument{plural}: {args}",
                )
            valid_call = False

        return valid_call, mapped

    def _are_mapped_subtypes(
        self, mapped1: list[MappedArgument[E]], mapped2: list[MappedArgument[E]]
    ) -> bool:
        """Check whether the given argument mappings are subtype/supertype of one another

        This function checks whether the argument mappings `mapped1` are subtypes
        of `mapped2`. If any of the parameter type in `mapped1` is not a subtype
        of the corresponding parameter in `mapped2`, `False` is returned.

        This is used to check whether a given overload is
        a more specific function/ a subtype of another.

        Args:
            mapped1 (list[MappedArgument]): the first argument mappings (subtype)
            mapped2 (list[MappedArgument]): the second argument mappings (supertype)

        Returns:
            bool: `True` if `mapped1` is a subtype of `mapped2`, `False` otherwise
        """
        by_expr: dict[E, Type] = {}
        for arg in mapped1:
            by_expr[arg.expr] = arg.argument.type

        for arg in mapped2:
            type2: Type = arg.argument.type
            type1: Type = by_expr[arg.expr]
            if not self.types.is_subtype(type1, type2):
                return False
        return True
