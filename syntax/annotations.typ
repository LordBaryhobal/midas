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

#let column-def = ```
{[`column-def` <!, ['identifier' ":"]> <"_", 'type-with-constraints'>]}
```

#let frame-def = ```
{[`frame-def` 'column-def' * ","]}
```

#let annotation = ```
{[`annotation` 'identifier' <!, ["[" 'frame-def' "]"]>]}
```

#let rules = (
  value,
  constraint,
  type-with-constraints,
  column-def,
  frame-def,
  annotation,
)

#set text(font: "Source Sans 3")

= Type annotation syntax

#for rule in rules {
  render(rule)
}

/*
#let by-name = (
  annotation: annotation,
  frame-def: frame-def,
  column-def: column-def,
  type-with-constraints: type-with-constraints,
  constraint: constraint,
  value: value,
)

#let substitute(base-rule) = {
  let new-rule = base-rule
  for (key, rule) in by-name.pairs() {
    new-rule = new-rule.replace("'" + key + "'", rule.text.slice(1, -1))
  }
  if new-rule != base-rule {
    new-rule = substitute(new-rule)
  }
  return new-rule
}

#let combined = raw(substitute(annotation.text))


#set page(flipped: true)
#render(combined)
*/