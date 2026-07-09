#import "@preview/curryst:0.6.0": prooftree, rule, rule-set
#import "@preview/gentle-clues:1.3.1" as gc
#import "@preview/lovelace:0.3.1": pseudocode-list

#set text(font: "Source Sans 3")
#show link: set text(fill: blue)
#set document(
  title: [Function subtyping rule],
)

#let req = math.op("req")

#align(center, title())


This document formalizes the logic used when checking whether a function is a subtype of another.

= Definitions

A *Parameter specification* has a list of positional-only parameters $P$, mixed parameters $M$ and keyword-only parameters $K$:
$ S = (P, M, K) $

A *Parameter* has an index $i$, a name $n$ and a required flag $r$:
$ p = (i, n, r) $

A *Function* has a param spec $S$ and a return type $R$:
$ F = (S, R) $

= Main rules

We want to define a rule for checking structural subtyping of functions, i.e. to check when $F_1 <: F_2$

There are two conditions to check:
#align(center, prooftree(
  rule(
    $Gamma tack S_2 <: S_1$,
    $Gamma tack R_1 <: R_2$,
    $Gamma tack F_1 <: F_2$,
  ),
))

The second condition is trivial to check.
The first condition is a bit more tricky.

For a parameter specification $S_2$ to be a subtype of another $S_1$, the latter needs to be fully compatible with any usages of the former. What this means is that #link(<cond-1>)[(1)] any argument that can be passed to $S_2$ must be accepted by $S_1$, and #link(<cond-2>)[(2)] $S_1$ must not have additional required arguments that are not in $S_2$. However, $S_1$ can have additional optional parameters not present in $S_2$.

After mapping parameters of $S_1$ and $S_2$, types must be checked such that if a parameter $p_i: T in S_1$ is mapped to a parameter $q_j: U in S_2$, $U <: T$.

= Detailed rules for *ParamSpec* subtyping

#gc.info(title: [Notation])[
  In the following equations:
  - the notation $S in.rev a^i: T$ will be used to denote that a parameter spec $S$ accepts an argument named $a$ at index $i$ of type $T$
  - the special name $alpha$ will be used to denote any argument without a specific name
  - the special name $phi$ will be used to denote any parameter without a specific name
  - $AA$ denotes the group of all arguments, i.e. $alpha in AA$
  - $PP$ denotes the group of all parameters, i.e. $p in PP$
  - $req(S, alpha)$ is a predicate checking whether $alpha$ is required in $S$
]

== Arguments of $S_2$ are compatible with $S_1$ <cond-1>

Formally, the condition is:
$
  forall alpha in AA, S_2 in.rev alpha => S_1 in.rev alpha
$

Let $S_1 = (P_1, M_1, K_1)$ and $S_2 = (P_2, M_2, K_2)$.

For each positional-only parameter $phi_i in P_2$, $phi_i in P_1 or phi_i in M_1$. A positional-only parameter of $S_2$ can either be positional-only or mixed in $S_1$. Additionally, $not req(S_2, phi_i) => not req(S_1, phi_i)$. If $phi_i$ is optional in $S_2$, it must also be optional in $S_1$ so that a call omitting it is valid.

Similarly, for each keyword-only parameter $p in K_2$, $p in K_1 or p in M_1$. A keyword-only parameter of $S_2$ can either be keyword-only or mixed in $S_1$. Additionally, $not req(S_2, p) => not req(S_1, p)$. If $p$ is optional in $S_2$, it must also be optional in $S_1$ so that a call omitting it is valid.

Finally, for mixed parameters, the rule is slightly more complex. Either there is a corresponding mixed parameter in $S_1$, or the parameter is covered by both a positional/mixed and a keyword/mixed parameter. In the second case, we must keep in mind that only one of the match will made at runtime, or maybe even none if the parameter is optional in $S_2$, meaning the parameters in $S_1$ _must_ be optional.

We can thus split the rule in two. $forall p_i in M_2$:
$
  cases(
    p_i in M_1 and not req(S_2, p_i) => not req(S_1, p_i),
    "or",
    underbrace((phi_i in P_1 or phi_i in M_1), "Positional") and
    underbrace((p in K_1 or p in M_1), "Keyword") and
    underbrace((not req(S_1, phi_i) and not req(S_1, p)), "Optional")
  )
$

== No additional required arguments in $S_1$ <cond-2>

Formally, the condition is:
$
  forall alpha in AA, S_1 in.rev alpha and req(S_1, alpha) => S_2 in.rev alpha and req(S_2, alpha)
$

Each parameter in $S_1$ that is not matched by a parameter in $S_2$ must be optional:
$
  forall p_i in S_1, p_i in.not S_2 => not req(S_1, p_i)
$
