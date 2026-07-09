# Local Variables:
# mode: makefile
# End:
set shell := ["bash", "-uc"]

build-docs:
  typst c --root . docs/manual.typ
  typst c --root . docs/function_subtyping.typ

tests:
  uv run -m tests

check-docstrings:
  uv run scripts/docstring_checker.py
