#import "@preview/codly:1.3.0": codly, codly-init
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

Fortunately, developers using IDEs or properly configured text editors can benefit from external type checkers such as MyPy which will perform static type analysis of their Python code. Some can also be configured to be very strict, forcing the user to make the whole code typable statically, thus avoiding any runtime type errors.

This is not the end of the problem though. Some parts of a program, especially in data related fields, may not be available at "compile-time". For example, a dataset can be loaded from an external file, or data can be fetched from an API, with no guarantees of having the expected format when analysing the code statically.

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
  caption: [Generated stubs],
) <qs-stubs>

== Using Midas in Python

You can now write your Python program as you would normally. You can import your custom types from the generated stubs file and use them in type annotations.

You can also import the `cast` and `unsafe_cast` functions from `midas.typing` to explictly cast a value to a specific type (see @cast for more information).

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
- *`type`* statements (see @type-stmt): to define a new type
- *`extend`* statements (see @extend-stmt): to define member of a type
- *`predicate`* statements (see @predicate-stmt): to define named predicates that can be used in constraint types

== Type Statement <type-stmt>

A *`type`* statement lets you define a new type. It requires a unique name and base type.

The simplest form of a *`type`* statement is:
```midas
type MyType = float
```

This statement defines a new type called `MyType` which is a subtype of `float`. `MyType` is a `float` but a `float` is not necessarily `MyType`.

=== Function types

A function type is written in a similar notation to Python function definitions:
```midas
type Repeater = fn(text: str, count: int) -> str
```

Midas supports positional-only, keyword-only and mixed arguments (using the `/` and `*` separators). You may omit the name of positional-only arguments. The return type is required.

Optional parameters can be indicated by adding a question mark (`?`) after their type:
```midas
type Repeater = fn(text: str, count: int, *, sep: str?) -> str
```

#gc.warning[
  Sink arguments (`*args`, `**kwargs`) are not currently supported.
]

=== Generic types

For more complex types, you might want to use type parameters. For example, to define a container, we might write:
```midas
type Container[T] = object
```

To better refine a generic type, you can also bound type parameters using the following syntax:
```midas
type Container[T <: float] = object
```

This can be read as "`Container` is a generic type which takes one type parameter `T` that must be a subtype of `float`".

You can use a generic type, i.e. instantiate it, by using a similar syntax with concrete type as arguments:

```midas
type MyContainer = Container[MyType]
```

Generic types can also take multiple parameters, which are then separated by commas:
```midas
type ZipCodeRegistry = dict[int, str]
```

The _body_ of a generic type, i.e. the right-hand side of the definition, can contain or even be equal to any number of its parameters.#footnote[The latter is not something that is expressible in standard Python, yet it brings a semantic distinction on top of structurally equivalent values.] For example, the following is a valid type statement:
```midas
type Price[T <: Currency] = T where _ > 0
```

=== Constraint types

A useful feature provided by Midas is the possibility to combine types with custom value constraints. For example, you might want to define a type for positive amounts of money:
```midas
type Money = float
type Income = Money where _ >= 0
```

Constraints can be combined with any type using the `where` keyword, followed by a predicate expression (see @predicate-stmt).

== Extend Statement <extend-stmt>

Type statements allow you to define new types, kind of like type aliases. However, a type might have properties or methods of its own. These might override those of the parent type or be brand new members.

This is where the `extend` statement comes into play. It allows defining members on a given type. Members can either be properties (`prop`) or methods (`def`). The only difference between the two is that methods must be functions and can be overloaded.

Here is a simple example showing how to define a property and a method on a custom type:
```midas
type MyType = float
extend MyType {
  prop norm: float
  def double: fn() -> MyType
}
```

An `extend` statement can appear anywhere after the type it extends has been defined.
You may want to overide Python's dunder methods to implement type checking for some basic operators, like `__add__` for the `+` operator.

```midas
type Money = float
extend Money {
  def __add__(Money, /) -> Money
  def __mul__(float, /) -> Money
}
```

When extending generic type, you must specify the whole type, including its parameter(s):
```midas
type Container[T <: float] = object
extend Container[T <: float] {
  prop content: T
  def set_content: fn(content: T) -> None
}
```

== Predicate Statement <predicate-stmt>

#TODO

== Casts <cast>

#TODO

= Supported Python Syntax <python-ref>

#TODO

