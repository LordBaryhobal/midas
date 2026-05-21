#import "@preview/fervojo:0.1.1": default-css, render

#let extra-css = ```css
svg.railroad .terminal rect {
  fill: #F7DCD4;
}
```
#let css = default-css() + bytes(extra-css.text)

#let variable = ```
{[`variable` 'identifier'*"."]}
```

#let value = ```
{[`value` <
  [`number` 'digit' * ! <!, ["." 'digit' * !]>],
  [`boolean` <"False", "True">],
  [`none` "None"]
>]}
```

#let lambda-value = ```
{[`lambda-value` <"_", 'value', 'variable'>]}
```

#let lambda-operator = ```
{[`lambda-operator` <">", "<", ">=", "<=", "==", "!=">]}
```

#let lambda = ```
{[`lambda` 'lambda-value' ['lambda-operator' 'lambda-value']*!]}
```

#let simple-type = ```
{[`simple-type` 'identifier' <!, "?">]}
```

#let template = ```
{[`template` "[" 'simple-type' "]"]}
```

#let type = ```
{[`type` 'identifier' <!, 'template'> <!, "?">]}
```

#let constraint = ```
{[`constraint` <'identifier', 'lambda'>]}
```

#let wrapped-constraint = ```
{[`wrapped-constraint` <'constraint', ["(" 'constraint' ")"]>]}
```

#let constraints = ```
{[`constraints` 'wrapped-constraint'*"&"]}
```

#let type-property = ```
{[`type-property` 'identifier' ":" 'type' <!, ["where" 'constraints']>]}
```

#let type-body = ```
{[`type-body` "{" <!, 'type-property'*!> "}"]}
```

#let type-statement = ```
{[`type-statement` "type" 'identifier' <!, 'template'> <[["(" 'type' ")"] <!, ["where" 'constraints']>], 'type-body'>]}
```

#let op-definition = ```
{[`op-definition` "op" <'identifier', ["__" 'identifier' "__"]> "(" 'type' ")" "->" 'type']}
```

#let extend-statement = ```
{[`extend-statement` "extend" 'type' "{" <!, 'op-definition'*!> "}"]}
```

#let predicate-statement = ```
{[`predicate-statement` "predicate" 'identifier' "(" 'identifier' ":" 'type' ")" "=" 'constraints']}
```

#let statement = ```
{[`statement` <'type-statement', 'extend-statement', 'predicate-statement'>]}
```

#let rules = (
  variable: variable,
  value: value,
  lambda-value: lambda-value,
  lambda-operator: lambda-operator,
  lambda: lambda,
  simple-type: simple-type,
  template: template,
  type: type,
  constraint: constraint,
  wrapped-constraint: wrapped-constraint,
  constraints: constraints,
  type-property: type-property,
  type-body: type-body,
  type-statement: type-statement,
  op-definition: op-definition,
  extend-statement: extend-statement,
  predicate-statement: predicate-statement,
  statement: statement,
)

#let inline = (
  "value",
  "variable",
  "lambda-operator",
  "template",
  "lambda",
  "simple-type",
  "wrapped-constraint",
  "type-property",
  "type-body",
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
  height: 8cm,
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
