#import "@preview/fervojo:0.1.1": default-css, render

#let extra-css = ```css
svg.railroad .terminal rect {
  fill: #F7DCD4;
}
```
#let css = default-css() + bytes(extra-css.text)

#let literal = ```
{[`literal` <
  [`number` 'digit' * ! <!, ["." 'digit' * !]>],
  [`boolean` <"False", "True">],
  [`string` <["\"" 'char'*! "\""], ["'" 'char'*! "'"]>],
  [`none` "None"]
>]}
```

#let grouping = ```
{[`grouping` "(" 'expression' ")"]}
```

#let primary = ```
{[`primary` <"_", 'literal', 'identifier', 'grouping'>]}
```

#let reference = ```
{[`reference` 'primary' <!, ["." 'identifier']*!>]}
```

#let call-args = ```
{[`call-args` "(" <!, <'expression', ['identifier' "=" 'expression']>*","#`Same rules as Python`> ")"]}
```

#let call = ```
{[`call` 'reference' <!, 'call-args'*!>]}
```

#let unary = ```
{[`unary` <[<"+", "-", "!"> 'unary'], 'call'>]}
```

#let factor = ```
{[`factor` 'unary'*<"*", "/">]}
```

#let term = ```
{[`term` 'factor'*<"+", "-">]}
```

#let comparison = ```
{[`comparison` 'term'*<">", "<", ">=", "<=">]}
```

#let equality = ```
{[`equality` 'comparison'*<"==", "!=">]}
```

#let expression = ```
{[`expression` 'equality'*"&"]}
```

#let constraint = ```
{[`constraint` 'expression']}
```

#let template-param = ```
{[`template-param` 'identifier' <!, ["<:" 'type']>]}
```

#let template = ```
{[`template` "[" <!, 'template-param'*","> "]"]}
```

#let type-property = ```
{[`type-property` 'identifier' ":" 'type']}
```

#let complex-type = ```
{[`complex-type` "{" <!, 'type-property'*!> "}"]}
```

#let named-type = ```
{[`named-type` 'identifier']}
```

#let type-args = ```
{[`type-args` "[" <!, 'type'*","> "]"]}
```

#let frame-schema = ```
{[`frame-schema` "[" <!, ['TOKEN' ":" 'type']*","> "]"]}
```

#let generic-type = ```
{[`generic-type` <["Frame" 'frame-schema'], ['named-type' <!, 'type-args'>]>]}
```

#let grouped-type = ```
{[`grouped-type` "(" 'type' ")"]}
```

#let base-type = ```
{[`base-type` <'grouped-type', 'complex-type', 'generic-type'>]}
```

#let constraint-type = ```
{[`constraint-type` 'base-type' <!, ["where" 'constraint']>]}
```

#let pos-param = ```
{[`pos-param` <!, ['identifier' ":"]> 'type' <!, "?">]}
```

#let kw-param = ```
{[`kw-param` 'identifier' ":" 'type' <!, "?">]}
```

#let param-spec = ```
{[`param-spec` "(" <!, <'pos-param', "/", "*", 'kw-param'>*",">#`Same rules as Python` ")"]}
```

#let func-type = ```
{[`func-type` "fn" 'param-spec' "->" 'type']}
```

#let type = ```
{[`type` <'func-type', 'constraint-type'>]}
```

#let alias-statement = ```
{[`alias-statement` "alias" 'identifier' "=" 'type']}
```

#let type-statement = ```
{[`type-statement` "type" 'identifier' <!, 'template'> "=" 'type']}
```

#let member-stmt = ```
{[`member-stmt` <"prop", "def"> 'identifier' ":" 'type']}
```

#let extend-statement = ```
{[`extend-statement` "extend" 'type' "{" <!, 'member-stmt'*!> "}"]}
```

#let predicate-statement = ```
{[`predicate-statement` "predicate" 'identifier' <!, 'param-spec'*!> "=" 'constraint']}
```

#let statement = ```
{[`statement` <'alias-statement', 'type-statement', 'extend-statement', 'predicate-statement'>]}
```

#let rules = (
  literal: literal,
  grouping: grouping,
  primary: primary,
  reference: reference,
  call-args: call-args,
  call: call,
  unary: unary,
  factor: factor,
  term: term,
  comparison: comparison,
  equality: equality,
  expression: expression,
  constraint: constraint,
  template-param: template-param,
  template: template,
  type-property: type-property,
  complex-type: complex-type,
  named-type: named-type,
  type-args: type-args,
  generic-type: generic-type,
  grouped-type: grouped-type,
  base-type: base-type,
  constraint-type: constraint-type,
  pos-param: pos-param,
  kw-param: kw-param,
  param-spec: param-spec,
  func-type: func-type,
  type: type,
  alias-statement: alias-statement,
  type-statement: type-statement,
  member-stmt: member-stmt,
  extend-statement: extend-statement,
  predicate-statement: predicate-statement,
  statement: statement,
)

#let inline = (
  "grouping",
  "literal",
  "template-param",
  "template",
  "type-property",
  "call-args",
  "complex-type",
  "type-args",
  "named-type",
  "grouped-type",
  "generic-type",
  "base-type",
  "constraint-type",
  "pos-param",
  "kw-param",
  "func-type",
  "member-stmt",
  "alias-statement",
  "type-statement",
  "extend-statement",
  "predicate-statement",
)

#set text(font: "Source Sans 3")

#title[Midas type definition syntax]

= Outline

#box(
  columns(
    2,
    outline(title: none),
  ),
  height: 15cm,
  stroke: 1pt,
  inset: 1em,
)

= Statements and expressions

#for (name, rule) in rules.pairs().rev() {
  [== #name]
  render(rule, css: css)
}

#let substitute(base-rule) = {
  let new-rule = base-rule
  for name in inline {
    let rule = rules.at(name)
    let replacement = rule.text.slice(1, -1).replace(regex("\[`.*?`"), "[")
    replacement = "[" + replacement + "#`" + name + "`]"
    new-rule = new-rule.replace(
      "'" + name + "'",
      replacement,
    )
  }
  if new-rule != base-rule {
    new-rule = substitute(new-rule)
  }
  return new-rule
}

#set page(flipped: true)

= Combined rules

#for (name, rule) in rules.pairs() {
  if not name in inline {
    [== #name]
    let combined = substitute(rule.text)
    render(raw(combined), css: css)
    //raw(block: true, combined)
  }
}
