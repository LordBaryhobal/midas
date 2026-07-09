import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class ArgDoc:
    name: str
    type: str
    optional: bool


@dataclass
class Param:
    name: str
    annotation: Optional[str]
    optional: bool


class Checker(ast.NodeVisitor):
    def _get_args(self, docstring: str) -> list[ArgDoc]:
        args: list[ArgDoc] = []

        in_args: bool = False
        for line in docstring.splitlines():
            if not in_args:
                if line == "Args:":
                    in_args = True
                continue

            # End of args
            if not line.startswith("    "):
                break

            # Continuation line
            if line.startswith("     "):
                continue

            line = line.strip()
            m = re.match(r"(?P<name>\w+) \((?P<type>.*?)(?P<opt>, optional)?\):", line)
            if m is None:
                continue

            args.append(
                ArgDoc(
                    name=m.group("name"),
                    type=m.group("type"),
                    optional=m.group("opt") is not None,
                )
            )

        return args

    def log(self, node: ast.FunctionDef, msg: str):
        loc: str = f"{node.name} L{node.lineno}:{node.col_offset+1}"
        print(f"    ({loc}) {msg}")

    def _is_ignored(self, node: ast.FunctionDef) -> bool:
        name: str = node.name
        if name.startswith("visit_") or name.startswith("_visit_"):
            return True
        if name.startswith("parse_") or name.startswith("_parse_"):
            return True
        if name.startswith("_print"):
            return True
        if name.startswith("_write"):
            return True
        if name.startswith("__") and name.endswith("__"):
            return True
        if name == "accept":
            return True
        node.decorator_list
        match node:
            case ast.FunctionDef(
                decorator_list=[
                    ast.Call(
                        func=ast.Name(id="method"),
                    ),
                ],
            ):
                return True
        return False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        docstring: Optional[str] = ast.get_docstring(node)
        func_name: str = node.name
        if docstring is None:
            if not self._is_ignored(node):
                self.log(node, f"Missing docstring for function {func_name}")
            return

        args_doc: list[ArgDoc] = self._get_args(docstring)
        by_name: dict[str, ArgDoc] = {}
        for doc in args_doc:
            if doc.name in by_name:
                self.log(node, f"Multiple documentation lines for argument {doc.name}")
            by_name[doc.name] = doc

        all_params: list[Param] = []

        pos_args: list[ast.arg] = node.args.posonlyargs
        mixed_args: list[ast.arg] = node.args.args
        kw_args: list[ast.arg] = node.args.kwonlyargs

        def add_param(arg: ast.arg, optional: bool):
            all_params.append(
                Param(
                    name=arg.arg,
                    annotation=(
                        ast.unparse(arg.annotation)
                        if arg.annotation is not None
                        else None
                    ),
                    optional=optional,
                )
            )

        n_pos: int = len(pos_args) + len(mixed_args)
        for i, arg in enumerate(pos_args):
            j: int = n_pos - i - 1
            optional: bool = j < len(node.args.defaults)
            add_param(arg, optional)

        for i, arg in enumerate(mixed_args):
            j: int = len(mixed_args) - i - 1
            optional: bool = j < len(node.args.defaults)
            add_param(arg, optional)

        for arg, default in zip(kw_args, node.args.kw_defaults):
            optional: bool = default is not None
            add_param(arg, optional)

        for param in all_params:
            doc: Optional[ArgDoc] = by_name.get(param.name, None)
            if doc is None:
                if param.name not in {"self", "cls"}:
                    self.log(
                        node, f"Missing documentation for parameter '{param.name}'"
                    )
                continue

            if doc.name != param.name:
                self.log(node, f"Documentation mismatch for '{param.name}': wrong name")

            if doc.type != param.annotation:
                self.log(node, f"Documentation mismatch for '{param.name}': wrong type")

            if doc.optional != param.optional:
                self.log(
                    node,
                    f"Documentation mismatch for '{param.name}': wrong optionality",
                )


def check_file(path: Path):
    source: str = path.read_text()
    tree = ast.parse(source)
    checker = Checker()
    checker.visit(tree)


def main():
    folder: Path = (Path(__file__).parent.parent / "midas").resolve()
    all_files = folder.rglob("*.py")
    for f in all_files:
        print(f.relative_to(folder))
        check_file(f)
        print()


if __name__ == "__main__":
    main()
