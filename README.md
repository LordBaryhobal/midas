<h1>Midas</h1>

<p align="center">
<img src="assets/icon.svg" width="64">
</p>

<img src="https://git.kb28.ch/HEL/midas/actions/workflows/tests.yaml/badge.svg">

*Midas* is a type system to _Maintain Integrity of Data with Annotated Structures_. In Greek mythology, [Midas](https://en.wikipedia.org/wiki/Midas) was a Phrygian king who was blessed with the gift of turning everything he touched into gold.

*Midas* aims at providing Python developers with a simple annotation system to enable compile-time integrity and data type checks, as well as generating runtime assertions.

This framework is being developed as part of a Bachelor's Thesis by Louis Heredero at HEI Sion.

<details>
<summary><strong>Table of Contents</strong></summary>

- [Requirements](#requirements)
- [Installation](#installation)
- [Commands](#commands)
  - [Type Checking](#type-checking)
  - [Compiling](#compiling)
  - [Formatting](#formatting)
  - [Highlighting](#highlighting)
  - [Dumping the AST](#dumping-the-ast)
  - [Dumping the Registry](#dumping-the-registry)
  - [Generating Stubs](#generating-stubs)
  - [Showing Type Judgements](#showing-type-judgements)
  - [Validating Definitions](#validating-definitions)
- [Tests](#tests)
- [Contributing](#contributing)
- [License](#license)
</details>


## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

## Installation

1. Clone the repository
   ```shell
   git clone https://git.kb28.ch/HEL/midas.git
   ```
2. Go in the project directory
   ```shell
   cd midas
   ```
3. Install the CLI as a user-wide tool
   ```shell
   uv tool install .
   ```
4. You can now run the `midas` command from anywhere
   ```shell
   midas --help
   ```

## Commands

Hereafter is a description of the commands you can use with Midas. For a full description, refer to [the manual](./docs/manual.pdf) or `midas <subcommand> --help`.

### Type Checking

```shell
midas check -t types.midas source.py
```

This command parses the given files and run the type checkers against the Midas definitions and Python program. Diagnostics are then printed showing warnings and errors.

### Compiling

```shell
midas compile -t types.midas source.py
```

With the `compile` command, you can process a source Python file, with any number of custom type definition files (`-t FILE` option), and the type checker will verify the coherence of your program and generate the runnable code with valid syntax and runtime assertions.

> [!WARNING]
> By default, any type checking error aborts the compilation and the generator is not run. You can bypass this behaviour with the `--ignore-errors` flag.
> Only use this flag if you know what you are doing as it will produce a possibly unsafe program and goes against the whole purpose of Midas

### Formatting

```shell
midas format types.midas
midas format types.midas -o formatted.midas
```

This command parses the given Midas file and outputs a pretty printed file from the AST.

### Highlighting

```shell
midas highlight source.py
midas highlight source.py -o highlighted.html
midas highlight types.midas
midas highlight types.midas -o highlighted.html
```

The `highlight` command takes in a source file (Python or Midas), runs the appropriate parser and outputs an HTML file containing the source code with added highlighting. This highlighting takes the form of hoverable annotations showing some of the parsed structures (e.g. a function definition, an assignment, a generic type, etc.)

The optional `-o FILE` option can be used to specify an output path. By default, the file is printed in stdout (equivalent to `-o -`).

### Dumping the AST

```shell
midas parse source.py
midas parse types.midas
```

For debugging purposes, you can output the AST parsed from a Python or Midas file. For Python files, the `--raw` flags lets you toggle the custom AST parsing. With `--raw`, the raw AST is returned, as produced by the builtin `ast` module. This flag has no effect on Midas files.

### Dumping the Registry

```shell
midas dump-registry -t types.midas
```

This command processes the given Midas definitions and dumps the contents of the types registry.

### Generating Stubs

```shell
midas stubs types.midas -o stubs.pyi
```

This command generates Python stubs from a Midas definition file

### Showing Type Judgements

```shell
midas types -t types.midas source.py
```

This command type checks the given Python source file and logs all typing judgements made by the type checker.

### Validating Definitions

```shell
midas validate types.midas
```

This command lets you validate a Midas definition file by running the parser and type checker, verifying syntax and references.

## Tests

Several snapshot tests are available to assert the good behaviour of the parser, type checker and generator. They can be run as follows:

```shell
uv run -m tests.midas run -a
uv run -m tests.python run -a
uv run -m tests.checker run -a
uv run -m tests.generator run -a
```

Alternatively, you can run all tests by executing the `tests` module directly:

```shell
uv run -m tests
```

When running only one test group, you may use one of the following subcommands.\
Not specifying any subcommand is equivalent to running `run -a`

**Available subcommands**:
- Run all tests: `run -a`
- Run specific tests: `run tests/cases/test1.py tests/cases/test2.py ...`
- Update all tests: `update -a`
- Update specific tests: `update tests/cases/test1.py tests/cases/test2.py ...`

## Contributing

Feel free to [open an issue](https://git.kb28.ch/HEL/midas/issues) to report a bug or if you experience any issues with Midas.

Contributions are also welcome so feel free to [open a pull request](https://git.kb28.ch/HEL/midas/pulls).

## License

Midas is distributed under the terms of the Apache-2.0 license. See [LICENSE](LICENSE) for details.