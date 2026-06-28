#import "@preview/modpattern:0.2.0": modpattern

#let TODO = block(
  width: 6em,
  height: 3em,
  stroke: red,
  fill: modpattern(
    size: (10pt, 10pt),
    line(
      start: (0%, 0%),
      end: (100%, 100%),
      stroke: gray.transparentize(60%) + 2pt,
    ),
  ),
  align(
    center + horizon,
    text(fill: red, size: 1.5em)[*TODO*],
  ),
)

#let _render-header(version, hash) = {
  let last-heading = query(heading.where(level: 1).before(here())).last(default: none)
  let next-heading = query(heading.where(level: 1).after(here())).first(default: none)

  let current-heading = if next-heading != none and next-heading.location().page() == here().page() {
    next-heading
  } else if last-heading != none {
    last-heading
  } else { none }

  let chapter = if current-heading != none {
    let body = current-heading.body
    if current-heading.numbering != none {
      let num = counter(heading).display(current-heading.numbering, at: current-heading.location())
      body = [#num #body]
    }
    body
  } else []

  grid(
    columns: (1fr, auto, 1fr),
    align: (left, center, right),
    document.title, [v#version - #hash], chapter,
  )
}

#let project(
  title: none,
  author: none,
  version: "0.0.1",
  hash: "abcdefgh",
  icon-path: none,
  doc,
) = {
  assert(title != none, message: "Please provide a title")

  set document(
    title: title,
    author: author,
  )
  set text(
    font: "Source Sans 3",
  )

  show std.title: set text(size: 1.5em)

  show heading.where(level: 1): it => {
    pagebreak()
    it
  }

  set page(
    header: context if counter(page).get().first() != 1 { _render-header(version, hash) },
    footer: context if counter(page).get().first() != 1 and page.numbering != none {
      align(center, counter(page).display(page.numbering, both: true))
    },
    numbering: "1 / 1",
  )

  set raw(syntaxes: path("midas.sublime-syntax"))

  // Title page
  align(center)[
    #std.title()

    v#version - #hash

    #if icon-path != none {
      v(1cm)
      image(icon-path)
    }
  ]

  outline()
  show heading: set heading(numbering: "I.1.")

  doc
}
