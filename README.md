# Midas

*Midas* is a type system to _Maintain Integrity of Data with Annotated Structures_. In Greek mythology, [Midas](https://en.wikipedia.org/wiki/Midas) was a Phrygian king who was blessed with the gift of turning everything he touched into gold.

*Midas* aims at providing Python developers with a simple annotation system to enable compile-time integrity and data type checks, as well as generating runtime assertions.

This framework is being developed as part of a Bachelor's Thesis by Louis Heredero at HEI Sion.

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

### Compiling

> [!NOTE]
> In the current state of the project, the `compile` command doesn't generate any runnable code, it only runs the parsers and type checker on the provided files

```shell
midas compile -t types.midas source.py
```

With the `compile` command, you can process a source Python file, with any number of custom type definition files (`-t FILE` option), and the type checker will verify the coherence of your program and generate the runnable code with valid syntax and runtime assertions.

The optional `-l FILE` option lets you produce a highlighted version of the source code showing diagnostics from the type checker (see [Highlighting](#highlighting))

### Highlighting

```shell
midas utils highlight source.py
# or
midas utils highlight types.midas
```

The `highlight` command takes in a source file (Python or Midas), runs the appropriate parser and outputs an HTML file containing the source code with added highlighting. This highlighting takes the form of hoverable annotations showing some of the parsed structures (e.g. a function definition, an assignment, a generic type, etc.)

The optional `-o FILE` option can be used to specify an output path. By default, the file is printed in stdout (equivalent to `-o -`).

### Dumping the AST

```shell
midas utils dump-ast source.py
# or
midas utils dump-ast types.midas
```

For debugging purposes, you can output the AST parsed from a Python or Midas file. For Python files, the `-p` flags lets you toggle the custom AST parsing. Without `-p`, the raw AST is returned, as produced by the builtin `ast` module. This flag has no effect on Midas files.

The optional `-o FILE` option can be used to specify an output path. By default, the file is printed in stdout (equivalent to `-o -`).

## Tests

Several snapshot tests are available to assert the good behaviour of the parsers and type checker. They can be run as follows:

```shell
uv run -m tests.midas run -a
uv run -m tests.python run -a
uv run -m tests.checker run -a
```

**Available subcommands:**
- Run all tests: `run -a`
- Run specific tests: `run tests/cases/test1.py tests/cases/test2.py ...`
- Update all tests: `update -a`
- Update specific tests: `update tests/cases/test1.py tests/cases/test2.py ...`
