//#import "@preview/codly:1.3.0": codly, codly-init
// Fix unaligned highlights in v0.15.0 ()
// See https://github.com/Dherse/codly/pull/132
#import "@local/codly:1.3.1": codly, codly-init

#import "@preview/codly-languages:0.1.10": codly-languages
#import "template.typ": TODO, project
#import "@preview/gentle-clues:1.3.1" as gc

#let midas-version = toml("../pyproject.toml").project.version
#let head-ref = read("../.git/HEAD").split(":").at(1).trim()
#let commit-hash = read("../.git/" + head-ref).slice(0, 8)

#show: project.with(
  title: [Midas User Manual],
  author: "Louis Heredero",
  version: midas-version,
  hash: commit-hash,
  icon-path: path("../assets/icon.svg"),
)

#show: codly-init
#codly(
  languages: codly-languages
    + (
      midas: (
        name: "Midas",
        color: rgb("#eedd47"),
        icon: box(
          image(
            "../assets/icon.svg",
            height: 130%,
            fit: "contain",
          ),
        ),
      ),
    ),
)

= Introduction

Python is a very popular programming language, especially in data sciences.
However, it has been designed for simplicity, distancing itself from typed languages such as Java or C to embrace dynamic typing.
What this means is that in Python, type checks are deferred to runtime when operations are concretely executed.

For developers, it might seem like a great way of simplifying the language and making it very flexible, but it does come with a cost.
Indeed, type errors are very easy to make in Python. While passing an integer where a string is expected might not be an issue in some cases, these are the sort of thing that can cause crashes or incorrect results without a clear diagnostic to help the user fix it.

Fortunately, developers using IDEs or properly configured text editors can benefit from external type checkers such as MyPy which will perform static type analysis of their Python code. Some can also be configured to be very strict, forcing the user to make the whole code typeable statically, thus avoiding any runtime type errors.

This is not the end of the problem though. Some parts of a program, especially in data related fields, may not be available at "compile-time". For example, a dataset can be loaded from an external file, or data can be fetched from an API, with no guarantees of having the expected format when analyzing the code statically.

In turn, that can cause a range of loud and silent errors at runtime. A malformed number will probably crash the program when trying to convert it, but a NaN in a series of value might just produce wrong results without any exception. Combine this with often long-running data-processing pipelines and this is how developers can waste hours of precious computation time.

Midas is a type system which can be used on top of Python to provide better type checking capabilities and gradual typing.
It aims at providing optional but strict type annotations and casting operations which can produce runtime assertions. It also allows the user to define dependent types with value constraints that are translated into runtime checks.

= Installation

Midas comes as a very light Python package that you can install on your system in a few simple steps.

== Requirements

Here below are the requirements for installing Midas. All Python dependencies will be installed by `uv` in the installation process described in @install-steps.

- Python 3.11+
- `uv`

== Steps <install-steps>

1. Clone the repository
  ```bash
  git clone https://git.kb28.ch/HEL/midas.git
  ```
2. Navigate inside the directory
  ```bash
  cd midas
  ```
3. Install Midas as a tool in your local user space
  ```bash
  uv tool install .
  ```

And that's it ! You can now use Midas commands anywhere, like this:
```bash
midas --help
```

= Quick Start

This chapter will give you the keys to quickly start using Midas in your project.

== Defining custom types

To begin with, you might want to define some custom types for your project, to avoid handling anonymous float values everywhere. To do so, create a `*.midas` file in your project, and write some definitions for your types. See @midas-ref for more information on syntax and features.

@qs-midas shows a simple example of what it might look like.

#codly(header: [types.midas])

#figure(
  ```midas
  type Meter = float
  extend Meter {
    def __add__: fn(Meter, /) -> Meter
    def __sub__: fn(Meter, /) -> Meter
  }

  type Coordinate = object
  extend Coordinate {
    prop x: Meter
    prop y: Meter
  }
  ```,
  caption: [Example Midas type definitions],
) <qs-midas>

You can check for any syntax error using the following command:
```bash
midas validate types.midas
```

When you are happy with your definitions, you can generate Python stubs to use in your source code. This allows other type checkers like MyPy to recognize your custom types and avoid reporting them as undefined. It can also help catch some type errors in your IDE.
```bash
midas stubs types.midas -o stubs.pyi
```

This command will generate a file as shown in @qs-stubs, providing stub classes to represent the type lattice including methods and properties.

#codly(header: [stubs.pyi])

#figure(
  ```pyi
  from __future__ import annotations

  class Meter(float):
      def __add__(self, _0: Meter, /) -> Meter: ...
      def __sub__(self, _0: Meter, /) -> Meter: ...

  class Coordinate(object):
      x: Meter
      y: Meter
  ```,
  caption: [Generated stubs from example definitions of @qs-midas],
) <qs-stubs>

== Using Midas in Python

You can now write your Python program as you would normally. You can import your custom types from the generated stubs file and use them in type annotations.

You can also import the `cast` and `unsafe_cast` functions from `midas.typing` to explicitly cast a value to a specific type (see @cast for more information).

An example Python script is shown in @qs-python, demonstrating how you can use custom types in type annotations. Notice the comments describing errors that will be caught by the type checker in @qs-type-checking.

#codly(header: [script.py])

#figure(
  ```python
  from lib import load_coordinate
  from midas.typing import cast
  from stubs import Coordinate, Meter

  p1 = cast(Coordinate, load_coordinate(0))
  p2 = cast(Coordinate, load_coordinate(1))

  diff_x = p2.x - p1.x
  diff_y = p2.y - p1.y

  dist = diff_x + diff_y

  p2.x += cast(Meter, 1)
  p2.y = True  # invalid, wrong type
  p2.z = 3  # invalid, no property 'z' on Coordinate
  p2.x.a = 3  # invalid, no properties on Meter
  ```,
  caption: [Example Python script],
) <qs-python>

== Type checking <qs-type-checking>

Now that you have defined some types and written a script, you can run the type checker with the following command. You can also skip this step and directly run the compilation command in @qs-compilation.

```bash
midas check -t types.midas script.py
```

== Compiling <qs-compilation>

The final step is to compile your code. This step will produce a runnable Python script, including runtime assertions generated by `cast` expressions.

```bash
midas compile -t types.midas script.py
python3 build/midas/script.py
```

= Midas Language Reference <midas-ref>

In this chapter, you will find a complete reference for the Midas definition language.

A `*.midas` file contains a number of statements, which can be:
- *`alias`* statements (see @alias-stmt): to define a new type alias
- *`type`* statements (see @type-stmt): to define a new type
- *`extend`* statements (see @extend-stmt): to define member of a type
- *`predicate`* statements (see @predicate-stmt): to define named predicates that can be used in constraint types

== Alias Statement <alias-stmt>

An *`alias`* statement lets you define a new type alias. It requires a unique name and base type.

While a `type` statement (see @type-stmt) allows generic definitions, aliases are purely a for givin an alternative name to a type.

#figure(
  ```midas
  alias MyType = float
  ```,
  caption: [Simple `alias` statement declaring a new type "`MyType`" equivalent to `float`],
) <midas-simple-alias>

This statement defines a new type called `MyType` which is equivalent to `float`. `MyType` and `float` can be used interchangeably.

== Type Statement <type-stmt>

A *`type`* statement lets you define a new type. It requires a unique name and base type.

The simplest form of a *`type`* statement is:
#figure(
  ```midas
  type MyType = float
  ```,
  caption: [Simple `type` statement declaring a new type "`MyType`" as a subtype of `float`],
) <midas-simple-type>

This statement defines a new type called `MyType` which is a subtype of `float`. `MyType` is a `float` but a `float` is not necessarily `MyType`.

=== Builtin / base types

A number of base types are provided out of the box, which can be used to derive other types.

They correspond to Python's builtin types:
```py object```,
```py str```,
```py float```,
```py int```,
```py bool```,
```py list```,
```py dict```,
```py None```.

Some differences are to be noted however.
1. ```py bool``` is not a subtype of ```py int```
2. ```py list``` are homogeneous, i.e. all items must be of the same type
3. ```py dict``` keys and values are homogeneous, i.e. all keys must be of the same type and all values must be of the same type (can be different from keys).

=== Function types

A function type is written in a similar notation to Python function definitions:
#figure(
  ```midas
  type Repeater = fn(text: str, count: int) -> str
  ```,
  caption: [Simple function type definition],
)

Midas supports positional-only, keyword-only and mixed arguments (using the `/` and `*` separators). You may omit the name of positional-only arguments. The return type is required.

Optional parameters can be indicated by adding a question mark (`?`) after their type:
#figure(
  ```midas
  type Repeater = fn(text: str, count: int, *, sep: str?) -> str
  ```,
  caption: [Function type definition with an optional keyword-only parameter],
)

#gc.warning[
  Sink arguments (`*args`, `**kwargs`) are not currently supported.
]

=== Constraint types

A useful feature provided by Midas is the possibility to combine types with custom value constraints. For example, you might want to define a type for positive amounts of money:

#figure(
  ```midas
  type Money = float
  type Income = Money where _ >= 0
  ```,
  caption: [Simple constraint type definition],
)

Constraints can be combined with any type using the `where` keyword, followed by a constraint expression (see @constraint-expr).

=== Generic types

For more complex types, you might want to use type parameters. For example, to define a container, we might write:
#figure(
  ```midas
  type Container[T] = object
  ```,
  caption: [Simple generic container type definition],
)

To better refine a generic type, you can also bound type parameters using the following syntax:
#figure(
  ```midas
  type Container[T <: float] = object
  ```,
  caption: [Generic container type definition with a bound],
)

This can be read as "`Container` is a generic type which takes one type parameter `T` that must be a subtype of `float`".\
You can use a generic type, i.e. instantiate it, by using a similar syntax with concrete type as arguments:

#figure(
  ```midas
  type MyContainer = Container[MyType]
  ```,
  caption: [Application of a generic type],
)

Generic types can also take multiple parameters, which are then separated by commas:
#figure(
  ```midas
  type ZipCodeRegistry = dict[int, str]
  ```,
  caption: [Application of a multi-parameter generic type],
)

The _body_ of a generic type, i.e. the right-hand side of the definition, can contain or even be equal to any number of its parameters.#footnote[The latter is not something that is expressible in standard Python, yet it brings a semantic distinction on top of structurally equivalent values.] For example, the following is a valid type statement:
#figure(
  ```midas
  type Price[T <: Currency] = T where _ > 0
  ```,
  caption: [Type parameters in a generic type's body],
)

=== `Column` / `Frame` types

To provide useful type-checking for data engineers, Midas offers two special types: `Column` and `Frame`.
Their goal is to help type check Pandas' `Series` and `DataFrame` respectively.

==== `Column`

The `Column` type is a generic type used to represent a `pandas.Series` object.
You can use it like any other generic type and it will provide type checking for some common methods and attributes offered by Pandas.

#figure(
  ```midas
  type Temperature = float
  alias Temperatures = Column[Temperature]
  ```,
  caption: [Simple column type definition],
)

==== `Frame` <frame-type>

The `Frame` type is a super-powered generic type used to represent a `pandas.DataFrame` object.
In place of type arguments, `Frame` accepts a schema, i.e. a series of column definitions.
@simple-frame show how you can define a simple frame type with 3 columns:
- `name`: a column of `Name` values
- `age`: a column of `int` values
- `height`: a column of `float where _ >= 0` values

Notice that you don't need to specify `Column` types.

#figure(
  ```midas
  type Name = str where len(_) != 0
  alias Data = Frame[
    name: Name,
    age: int,
    height: float where _ >= 0
  ]
  ```,
) <simple-frame>

#pagebreak()

== Extend Statement <extend-stmt>

Type statements allow you to define new types, kind of like type aliases. However, a type might have properties or methods of its own. These might override those of the parent type or be brand new members.

This is where the `extend` statement comes into play. It allows defining members on a given type. Members can either be properties (`prop`) or methods (`def`). The only difference between the two is that methods must be functions and can be overloaded.

Here is a simple example showing how to define a property and a method on a custom type:
#figure(
  ```midas
  type MyType = float
  extend MyType {
    prop norm: float
    def double: fn() -> MyType
  }
  ```,
  caption: [Simple `extend` statement defining a property and a method],
)

An `extend` statement can appear anywhere after the type it extends has been defined.
You may want to override Python's dunder methods to implement type checking for some basic operators, like `__add__` for the `+` operator.

#figure(
  ```midas
  type Money = float
  extend Money {
    def __add__(Money, /) -> Money
    def __mul__(float, /) -> Money
  }
  ```,
  caption: [Simple `extend` statement overriding some dunder methods],
)

When extending generic type, you must specify the whole type, including its parameter(s):
#figure(
  ```midas
  type Container[T <: float] = object
  extend Container[T <: float] {
    prop content: T
    def set_content: fn(content: T) -> None
  }
  ```,
  caption: [Generic `extend` statement using type parameters in the declared members],
)

#pagebreak()

== Predicate Statement <predicate-stmt>

A *`predicate`* statement lets you define a named constraint expression, like a function, which can then be used in other constraint expressions (either in other predicate statements or in constraint types). See @constraint-expr for more information about the syntax of constraint expressions.

The left-hand side of a predicate statement is written as a function signature, without a return type. The right-hand side is a constraint expression. For example:
#figure(
  ```midas
  predicate is_positive(v: float) = v >= 0
  ```,
  caption: [Simple `predicate` statement defining an `is_positive` predicate],
)

The left-hand side can also be curried to allow partial application. For example:
#figure(
  ```midas
  predicate in_range(mn: float, mx: float)(v: float) = mn <= v & v <= mx
  predicate is_ratio = in_range(0.0, 1.0)
  ```,
  caption: [Curried `predicate` statement and partial application],
) <midas-predicate-partial>

Notice that the second predicate statement doesn't take any parameters. This is simply a partial application of another predicate, kind of like an alias. You can use it in other expressions to finalize the call:
#figure(
  ```midas
  type Efficiency = float where is_ratio(_)
  ```,
  caption: [Constraint type definition using the partially applied predicate from @midas-predicate-partial],
)

Of course you can also directly call `in_range`:
#figure(
  ```midas
  type Efficiency = float where in_range(0.0, 1.0)(_)
  ```,
  caption: [Full call of curried predicate from @midas-predicate-partial],
)

When compiled, named predicates are translated to Python functions which are used in runtime assertions. Only predicates that are referenced are compiled.

#pagebreak()
== Constraint Expressions <constraint-expr>

*Constraint expressions* are Python-like expressions which can appear in *`predicate`* statements or in constraint types.

They can contain comparisons, simple computations, logical operations and must evaluate to a boolean value.

Context is quite restricted inside these expressions. You can only reference some builtin functions, such as type constructors (`float(...)`, `str(...)`, etc.), parameters of predicate statements, and named predicates. In constraint type, the special variable `_` can be used to reference the value targeted by the type. For example:

#figure(
  ```midas
  predicate not_nan(v: float) = v != float("nan")
  type RealFloat = float where not_nan(_)
  ```,
  caption: [Example constraint expressions],
) <ex-constraint-expr>

In the predicate statement (@ex-constraint-expr:1), we reference the parameter `v` and the builtin `float` function.
In the constraint type definition (@ex-constraint-expr:2), we then reference the named predicate `not_nan`, passing the value targeted by the type itself ( `_` )

= Supported Python Syntax <python-ref>

Midas integrates naturally in Python via type annotations. Through generated stubs, even other type checker can detect your custom types (see @cmd-stubs).

It has been designed to leave the user free of typing any amount of their code but be strict about the parts that are annotated. By default, any untyped Python expression is assigned `UnknownType`.

Any operation is permitted on `UnknownType` and will result in `UnknownType` values.

The moment an expression can be typed, that be thanks to an annotation or a literal value, the type checker kicks in and will validate your statements.

Because Python is very flexible language with many features, some expressions and statements might be more complex to properly type check, thus only a subset of the Python language is fully supported. This chapter lists all supported features of Python and how they affect type checking.

Some examples are presented in the following sections in the form of code blocks. Highlights in the code blocks indicate the type assigned to each expression by the type checker. Some types may be omitted for readability. For example:

#codly(
  highlights: (
    (
      line: 1,
      start: 5,
      fill: green,
      tag: [_int_],
    ),
    (
      line: 2,
      start: 7,
      end: 7,
      fill: green,
      tag: [_int_],
    ),
  ),
)

```python
v = 3
print(v)
```

== Literals

Literal Python values are type checked using builtin types. Lists and dictionaries of literals are also typed liked literals. This does not include comprehension lists/dicts (```py [. for . in .]```), nor formatted strings (```py f"..."```). @supported-literals shows the list of supported literal values and their type.

#let supported-literals = table(
  columns: 2,
  table.header[*Example value*][*Judged Type*],
  ```py 42```, ```py int```,
  ```py 3.14```, ```py float```,
  ```py True```, ```py bool```,
  ```py "Midas"```, ```py str```,
  ```py None```, ```py None```,
  ```py [1, 2, 3]```, ```py list[int]```,
  ```py {1: "One", 2: "Two"}```, ```py dict[int, str]```,
  ```py ("1", 1, True)```, ```py tuple[str, int, bool]```,
)

#figure(
  supported-literals,
  caption: [Supported literal values and their judged types],
) <supported-literals>

== Assignments

Variable assignments allow assigning a new value to a variable. For the type checker, this implies two things:
1. If the variable was not already declared in the current scope, it is declared at that point with the type of the right-hand side expression
2. If the variable was already declared, the type of the right-hand side expression is checked against the declared type of the variable. Only a subtype of the variable's type can be assigned to it

Once a variable has been given a type, it cannot be changed in the same scope.

The walrus operator (```py :=```) is not currently supported.

A simple annotation declaration, without assigning a value, is enough to declare a variable. For example:
#figure(
  ```python
  var: float
  ```,
  caption: [Bare Python variable annotation without assignment],
)

Because unpacking is not supported, assigning to multiple values is also not handled by the type checker.
For more information about type annotations, see @type-annotations

== Arithmetic

- All basic binary operators are supported, through dunder methods.
- All comparison operators except ```py in``` are supported.
- All unary operators are supported (`+`, `-`, `~`).
- All logical operators are supported (```py and```, ```py or```, ```py not```).

== Ternary operator

The ternary operator ```py . if . else .``` is supported. As for `if` statements (see @if-else), the test expression must be a boolean. Additionally, both branches must be of the same type.

For example:
#codly(
  highlights: (
    (
      line: 1,
      start: 10,
      end: 44,
      tag: [_str_],
      fill: blue,
    ),
    (
      line: 1,
      start: 11,
      end: 16,
      tag: [_str_],
      fill: green,
    ),
    (
      line: 1,
      start: 39,
      end: 43,
      tag: [_str_],
      fill: green,
    ),
    (
      line: 1,
      start: 21,
      end: 32,
      tag: [_bool_],
      fill: green,
    ),
  ),
)
#figure(
  ```python
  parity = ("even" if num % 2 == 0 else "odd")
  ```,
  caption: [Typing of ternary operator],
)

== Control flow

Some control flow features are supported. For the limited code of this project, not all constructs are supported. The following are those currently handled and typ checked by Midas.

=== `if` / `elif` / `else` <if-else>

Conditional statements are checked relatively strictly by Midas. The test expression, i.e. what comes after the ```py if``` keyword, must be a boolean. While Python allows introducing and leaking new variables from inside an ```py if``` statement, Midas will strictly forbid leaks by restraining bindings to the scope they are defined in. For example, the following Python code will not compile with Midas:
#figure(
  ```python
  age = 22
  if age >= 18:
      msg = "You're an adult"
  else:
      msg = "You're still a child"
  print(msg)  # -> unknown variable 'msg'
  ```,
  caption: [`if`/`else` statement cannot leak variables],
)

=== `for` loops

Simple forms of `for` loops can be used, that is using a single variable and iterating over an object implementing the `__getitem__` method. Like above in @if-else, leaking variables from inside the loop is ignored.

`for`-`else` statements are not supported. `while` loops are also not supported.

== Functions

You can define functions as usual and the type checker will do its best to type it. Apart from argument sinks (`*args`, `**kwargs`), all forms of parameter specifications are supported (positional-only, keyword-only, mixed, optional).

As for the rest of your code, type annotations are optional, but recommended. If you omit the return type hint, the type checker will try to infer it from the function body and its return statements. If you did specify a return type, all return paths must return values that are subtypes of the type hint.

#codly(
  highlights: (
    (
      line: 2,
      start: 12,
      end: 16,
      tag: [_float_],
      fill: green,
    ),
    (
      line: 2,
      start: 12,
      tag: [_float_],
      fill: blue,
    ),
    (
      line: 3,
      start: 10,
      end: 15,
      tag: [_(value: float) -> float_],
      fill: green,
    ),
    (
      line: 3,
      start: 17,
      end: 19,
      tag: [_float_],
      fill: green,
    ),
    (
      line: 3,
      start: 10,
      tag: [_float_],
      fill: blue,
    ),
  ),
)
#figure(
  ```python
  def double(value: float) -> float:
      return value * 2
  result = double(4.0)
  ```,
  caption: [Typing of function's body and call],
)

Anonymous functions (```py lambda```) are not yet supported

== Casts <cast>

#gc.info[
  The functions discussed in this section are provided by the `midas.typing` submodule. You can import them in your script like so:
  #figure(
    ```python
    from midas.typing import cast, unsafe_cast
    ```,
    caption: [Importing cast functions],
  )
]

Sometimes, you may want to use a value whose type is not known to the type checker in a place where it expects a particular type. In that case, if you do know that the runtime type will correspond to what is expected, you can use a `cast` expression.

Similar to the `cast` function from the `typing` package of Python's Standard Library, it allows telling the type checker that a value has a given type. While `typing`'s function doesn't have any runtime side-effect, Midas' will generate runtime assertions, ensuring that your statement is true when running the code. What cannot be checked statically is checked at runtime.

In the following example, a runtime check would be generated to ensure that the value is indeed a `float` and that it satisfies the type's constraint (i.e. `>= 0`):

#codly(
  highlights: (
    (
      line: 1,
      start: 35,
      end: 47,
      tag: [_UnknownType_],
      fill: red,
    ),
    (
      line: 2,
      start: 7,
      end: 17,
      tag: [_PositiveFloat_],
      fill: green,
    ),
  ),
)
#figure(
  ```python
  typed_value = cast(PositiveFloat, unknown_value)
  print(typed_value)
  ```,
  caption: [Typing of `cast` expression],
)

#gc.warning[
  Assertions are statements inserted just before a statement using a `cast` expression. This means that the expression is evaluated _before_ its actual intended usage location, which might cause issues if you rely on logical operator short-circuiting. See @eager-eval for more information.
]

There may be some cases where the cost of checking a value at runtime is simply not worth the safety, for example when dealing with a big dataset. If do wish so, you can use `unsafe_cast` which will only tell the type checker the type of the value, without generating a runtime assertion. This maps to the default behavior of `typing`'s own `cast` function.

If the value passed to `cast` or `unsafe_cast` is a literal (e.g. an integer, a string, a list of literals, etc.), the assertion is evaluated _at compile-time_ and no runtime assertion is generated.

== Annotations / Type Hints <type-annotations>

Vanilla Python already lets you use type hints to specify the type of variables and function parameters.

Midas use them to type check your code. Additionally, it allows you to use a special syntax to define a `Frame` types directly in these annotations.

Because these annotations are not interpretable by Python, your integrated type checker might complain loudly about them being invalid.
A workaround is to silence it by adding a type comment at the end of the line, as shown in @silence-errors.

#figure(
  ```python
  var: Frame[name: str, age: float]  # type: ignore # noqa: F821
  ```,
  caption: [MyPy's and Pylance's complaints about custom type annotation can be silenced with type comments],
) <silence-errors>

=== Frame type annotation

The syntax is similar to how you can define frame types in the Midas language (see @frame-type). The only difference is that types can only be name references; you cannot inline constraint types.

The example of @python-frame-type shows how you can annotate a dataframe with some columns directly in Python.

#figure(
  ```python
  df: Frame[name: Name, age: float, height: Length[Meter]] = ...
  ```,
  caption: [Frame type annotation in Python],
) <python-frame-type>

= Commands <commands>

#TODO

== Type Checking (`check`) <cmd-check>
== Compiling (`compile`) <cmd-compile>
== Formatting (`format`) <cmd-format>
== Highlighting (`highlight`) <cmd-highlight>
== Dumping the AST (`parse`) <cmd-parse>
== Dumping the Registry (`dump-registry`) <cmd-registry>
== Generating Stubs (`stubs`) <cmd-stubs>
== Showing Type Judgements (`types`) <cmd-types>
== Validating Definitions (`validate`) <cmd-validate>

= Known limitations <limitations>

== Eager evaluation in runtime assertions <eager-eval>

The process of generating assertions to ensure safety at runtime, mainly for `cast` expressions, leads to the creation of aliases for the expressions being casted. These alias definitions eagerly evaluate before the assertion, and most importantly before the real usage location. This means that you should avoid using `cast` expressions inside logical expressions like `and` or `or`, because the normal "short-circuit" behavior will be irrelevant to the evaluations of the operands.

For example:

#figure(
  ```py
  def foo():
      print("Foo")
      return True
  def bar():
      print("Bar")
      return True
  result = foo() or bar()
  # Foo
  # Bar
  ```,
  caption: [Runtime assertions may eagerly evaluate expressions and bypass logical operator's short-circuit],
)
