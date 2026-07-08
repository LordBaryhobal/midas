#import "@preview/fervojo:0.1.1": default-css, render

#let extra-css = ```css
svg.railroad .terminal rect {
  fill: #F7DCD4;
}
```
#let css = default-css() + bytes(extra-css.text)

#let type-args = ```
{[`type-args` "[" <!, 'type'*","> "]"]}
```

#let frame-schema = ```
{[`frame-schema` "[" <!, [[<'identifier', "_"> ":"]? 'type']*","> "]"]}
```

#let type = ```
{[`type` <
  ["Frame" 'frame-schema'],
  ['identifier' <!, 'type-args'>]
>]}
```

#let rules = (
  type-args: type-args,
  frame-schema: frame-schema,
  type: type,
)

#let inline = (
  "type-args",
  "frame-schema",
)

#set text(font: "Source Sans 3")

#title[Supported Python annotation syntax]

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
