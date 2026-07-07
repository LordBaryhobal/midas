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

#let _unshift-prefix(prefix, content) = context {
  pad(left: -measure(prefix).width, prefix + content)
}

#let project(
  title: none,
  author: none,
  version: "0.0.1",
  hash: none,
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

  set raw(syntaxes: path("midas.sublime-syntax"))

  let front-page() = {
    let version-name = [v#version]
    if hash != none {
      version-name = [#version-name - #hash]
    }
    align(center)[
      #{
        set text(size: 1.5em)
        std.title()
      }

      #version-name

      #if icon-path != none {
        v(1cm)
        image(icon-path)
      }
    ]
    pagebreak()
  }

  let outlines() = {
    outline()
    pagebreak()
    outline(
      title: [List of Listings],
      target: figure.where(kind: raw),
    )

    outline(
      title: [List of Tables],
      target: figure.where(kind: table),
    )
  }

  let main() = {
    // Adapted from https://github.com/hei-templates/hei-synd-thesis/blob/7d2b941197babae0bf3afd4e5914754e09a64001/lib/template-thesis.typ#L242-L261
    show heading.where(level: 1): it => {
      pagebreak()

      set text(size: 1.5em)
      set block(above: 1.2em, below: 1.2em)
      if it.numbering != none {
        let num = numbering(it.numbering, ..counter(heading).at(it.location()))
        let prefix = num + h(1em)
        _unshift-prefix(prefix, it.body)
      } else {
        it
      }
    }

    show heading.where(level: 2): it => {
      if it.numbering != none {
        let num = numbering(it.numbering, ..counter(heading).at(it.location()))
        _unshift-prefix(num + h(0.8em), it.body)
      } else {
        it
      }
    }

    set page(
      header: context _render-header(version, hash),
      footer: context if page.numbering != none {
        align(center, counter(page).display(page.numbering, both: true))
      },
      numbering: "1 / 1",
    )

    show heading: set heading(numbering: "I.1.")
    counter(page).update(1)
    doc
  }

  front-page()
  outlines()
  main()
}
