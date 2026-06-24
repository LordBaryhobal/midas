#import "template.typ": TODO, project

#let midas-version = toml("../pyproject.toml").project.version
#let head-ref = read("../.git/HEAD").split(":").at(1).trim()
#let commit-hash = read("../.git/" + head-ref).slice(0, 8)

#show: project.with(
  title: [Midas User Manual],
  author: "Louis Heredero",
  version: midas-version,
  hash: commit-hash,
  icon-path: path("../assets/icon.svg"),
)

= Introduction

#TODO

= Installation

#TODO

= Quick Start

This chapter will give you the keys to quickly start using Midas in your project.

#TODO
