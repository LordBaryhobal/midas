#import "@preview/fervojo:0.1.1": render

#let value = ```
{[`value` <
  [`number` 'digit' * ! <!, ["." 'digit' * !]>],
  [`boolean` <"False", "True">],
  [`none` "None"]
>]}
```

#let constraint = ```
{[`constraint` <"_", 'value'> <">", "<", ">=", "<=", "==", "!="> <"_", 'value'>]}
```

#let type-with-constraints = ```
{[`type-with-constraints` 'identifier' <!, ["+" "(" 'constraint' ")"] * !>]}
```

#let type-property = ```
{[`type-property` 'identifier' ":" 'type-with-constraints']}
```

#let type-body = ```
{[`type-body` "{" <!, 'type-property'*!> "}"]}
```

#let operation-type = ```
{[`operation-type` "<" 'type-with-constraints' ">"]}
```

#let type-statement = ```
{[`type-statement` "type" 'identifier' "<" 'type-with-constraints'*"," ">" <!, 'type-body'>]}
```

#let operation-statement = ```
{[`operation-statement` "op" 'operation-type' "operator" 'operation-type' "=" 'operation-type']}
```

#let constraint-statement = ```
{[`constraint-statement` "constraint" 'identifier' "=" 'constraint']}
```

#let statement = ```
{[`statement` <'type-statement', 'operation-statement', 'constraint-statement'>]}
```

#let rules = (
  value,
  constraint,
  type-with-constraints,
  type-property,
  type-body,
  operation-type,
  type-statement,
  operation-statement,
  constraint-statement,
  statement,
)

#set text(font: "Source Sans 3")

= Midas type definition syntax

#for rule in rules {
  render(rule)
}

/*
#let by-name = (
  value: value,
  constraint: constraint,
  type-with-constraints: type-with-constraints,
  type-property: type-property,
  type-body: type-body,
  operation-type: operation-type,
  type-statement: type-statement,
  operation-statement: operation-statement,
  constraint-statement: constraint-statement,
)

#let substitute(base-rule) = {
  let new-rule = base-rule
  for (key, rule) in by-name.pairs() {
    new-rule = new-rule.replace("'" + key + "'", rule.text.slice(1, -1))
  }
  if new-rule != base-rule {
    new-rule = substitute(new-rule)
  }
  return new-rule.replace(regex("`.*?`"), "")
}

#let combined = raw(substitute(statement.text))


#set page(flipped: true)
#render(combined)
*/