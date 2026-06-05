#import "@preview/fervojo:0.1.1": default-css, render

#let extra-css = ```css
svg.railroad .terminal rect {
  fill: #F7DCD4;
}
```
#let css = default-css() + bytes(extra-css.text)

#let value = ```
{[`value` <
  [`number` 'digit' * ! <!, ["." 'digit' * !]>],
  [`boolean` <"False", "True">],
  [`none` "None"]
>]}
```

#let grouping = ```
{[`grouping` "(" 'constraint' ")"]}
```

#let primary = ```
{[`primary` <"_", 'value', 'identifier', 'grouping'>]}
```

#let reference = ```
{[`reference` 'primary' <!, ["." 'identifier']*!>]}
```

#let unary = ```
{[`unary` <[<!, "-"> 'unary'], 'reference'>]}
```

#let comparison = ```
{[`comparison` 'unary'*<">", "<", ">=", "<=">]}
```

#let equality = ```
{[`equality` 'comparison'*<"==", "!=">]}
```

#let constraint = ```
{[`constraint` 'equality'*"&"]}
```

#let simple-type = ```
{[`simple-type` 'identifier' <!, "?">]}
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

#let type-params = ```
{[`type-params` "[" <!, 'type'*","> "]"]}
```

#let generic-type = ```
{[`generic-type` 'named-type' <!, 'type-params'>]}
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

#let type = ```
{[`type` 'constraint-type']}
```

#let type-statement = ```
{[`type-statement` "type" 'identifier' <!, 'template'> "=" 'type']}
```

#let op-definition = ```
{[`op-definition` "op" 'identifier' "(" 'type' ")" "->" 'type']}
```

#let extend-statement = ```
{[`extend-statement` "extend" 'type' "{" <!, 'op-definition'*!> "}"]}
```

#let predicate-statement = ```
{[`predicate-statement` "predicate" 'identifier' "(" 'identifier' ":" 'type' ")" "=" 'constraint']}
```

#let statement = ```
{[`statement` <'type-statement', 'extend-statement', 'predicate-statement'>]}
```

#let rules = (
  value: value,
  grouping: grouping,
  primary: primary,
  reference: reference,
  unary: unary,
  comparison: comparison,
  equality: equality,
  constraint: constraint,
  simple-type: simple-type,
  template-param: template-param,
  template: template,
  type-property: type-property,
  complex-type: complex-type,
  named-type: named-type,
  type-params: type-params,
  generic-type: generic-type,
  grouped-type: grouped-type,
  base-type: base-type,
  constraint-type: constraint-type,
  type: type,
  type-statement: type-statement,
  op-definition: op-definition,
  extend-statement: extend-statement,
  predicate-statement: predicate-statement,
  statement: statement,
)

#let inline = (
  "grouping",
  "value",
  "template-param",
  "template",
  "simple-type",
  "type-property",
  "complex-type",
  "type-params",
  "named-type",
  "grouped-type",
  "generic-type",
  "base-type",
  "constraint-type",
  "op-definition",
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
  height: 9cm,
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
