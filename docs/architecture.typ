#import "@preview/cetz:0.5.2": canvas, draw

#let diagram-only = false

#set document(
  title: [Midas Architecture],
  //author: "Louis Heredero",
)

#set text(
  font: "Source Sans 3",
)

#let diagram = canvas({
  let framed = draw.content.with(
    padding: (x: .8em, y: 1em),
    frame: "rect",
    stroke: black,
  )
  let arrow = draw.line.with(mark: (end: ">", fill: black))
  framed(
    (0, 0),
    name: "python-parser",
  )[Python parser]

  draw.content(
    (rel: (0, 1), to: "python-parser.north"),
    padding: 5pt,
    anchor: "south",
    name: "source-py",
  )[_`source.py`_]
  arrow("source-py", "python-parser")

  framed(
    (rel: (3, 0), to: "python-parser.east"),
    anchor: "west",
    name: "custom-parser",
    align(center)[Custom python\ parser],
  )

  arrow("python-parser", "custom-parser", name: "arrow-python-ast")
  draw.content(
    "arrow-python-ast",
    anchor: "south",
    padding: 5pt,
  )[`ast.Module`]

  framed(
    (rel: (-3, -2), to: "custom-parser.south"),
    anchor: "east",
    name: "python-resolver",
  )[Python Resolver]
  arrow(
    "custom-parser",
    ((), "|-", "python-resolver.east"),
    "python-resolver",
    name: "arrow-python-custom-ast",
  )
  draw.content(
    (rel: (1.5, 0), to: "arrow-python-custom-ast.end"),
    padding: 5pt,
    anchor: "south",
  )[P-AST#footnote[#strong[P]ython *AST*]<fn-past>]
  draw.content(
    "python-resolver.west",
    padding: 5pt,
    anchor: "south-east",
  )[Resolved P-AST@fn-past]

  draw.circle(
    (rel: (1, -2), to: "custom-parser.south-east"),
    radius: .4,
    name: "midas-loader",
  )
  arrow(
    "custom-parser",
    "midas-loader",
    name: "arrow-load-midas",
    mark: (end: (symbol: ">", fill: black), start: "o"),
  )
  draw.content(
    "arrow-load-midas",
    anchor: "west",
    padding: 5pt,
  )[```python midas.using("types.midas")```]

  framed(
    (rel: (0, -2), to: "midas-loader.south"),
    name: "midas-parser",
  )[Midas lexer/parser]
  arrow("midas-loader", "midas-parser", name: "arrow-midas-source")
  draw.content(
    "arrow-midas-source",
    anchor: "west",
    padding: 5pt,
  )[_`types.midas`_]


  framed(
    (rel: (-2, 0), to: "midas-parser.west"),
    anchor: "east",
    name: "midas-resolver",
  )[Midas Resolver]
  arrow("midas-parser", "midas-resolver", name: "arrow-midas-ast")
  draw.content(
    "arrow-midas-ast",
    anchor: "south",
    padding: 5pt,
  )[M-AST#footnote[#strong[M]idas *AST*]<fn-mast>]

  framed(
    (rel: (-3, 0), to: "midas-resolver.west"),
    anchor: "east",
    name: "checker",
  )[Checker]
  arrow("midas-resolver", "checker", name: "arrow-type-ctx")
  arrow(
    "python-resolver",
    ((), "-|", "checker.north"),
    "checker",
  )
  draw.content(
    "arrow-type-ctx",
    anchor: "south",
    padding: 5pt,
  )[Types context]
})

#show: doc => if diagram-only {
  set page(width: auto, height: auto, margin: .5cm)
  diagram
} else { doc }

#align(center, title())

#v(1cm)

#figure(
  diagram,
  caption: [Midas type-checker architecture],
)

== Components

- *Python parser*: builtin Python AST parser, extracts abstract syntax from the raw Python source (```python ast.parse(...)```)
- *Custom python parser*: converts the raw Python AST into custom, more suitable constructs, especially for type annotations
- *Python resolver*: resolves bindings and references, tracks binding scopes
- *Midas lexer/parser*: parses a Midas type definition file and extracts its AST
- *Midas resolver*: walks the AST and fills the environment with the defined types and operations
- *Checker*: evaluates expressions and checks type coherence
