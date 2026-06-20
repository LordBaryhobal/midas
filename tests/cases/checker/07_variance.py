from _ import (
    T1,
    T2,
    Coco,
    Cocontra,
    Contraco,
    Contracontra,
    Contravariant,
    Covariant,
    Invariant,
    Unused,
)

unused: Unused
covariant: Covariant
contravariant: Contravariant
invariant: Invariant
coco: Coco
cocontra: Cocontra
contraco: Contraco
contracontra: Contracontra
t1: T1
t2: T2

# Dummy print to prudce judgements for the expressions
print(
    unused,
    covariant,
    contravariant,
    invariant,
    coco,
    cocontra,
    contraco,
    contracontra,
    t1,
    t2,
)

cov1: Covariant[float]
cov2: Covariant[int]
cov1 = cov2  # Ok because int <: float => Covariant[int] <: Covariant[float]
cov2 = cov1  # Invalid

contra1: Contravariant[float]
contra2: Contravariant[int]
contra1 = contra2  # Invalid
contra2 = contra1  # Ok because int <: float => Covariant[float] <: Covariant[int]

inv1: Invariant[float]
inv2: Invariant[int]
inv1 = inv2  # Invalid
inv2 = inv1  # Invalid
