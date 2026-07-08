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

unused: Unused = object()
covariant: Covariant = object()
contravariant: Contravariant = object()
invariant: Invariant = object()
coco: Coco = object()
cocontra: Cocontra = object()
contraco: Contraco = object()
contracontra: Contracontra = object()
t1: T1 = object()
t2: T2 = object()

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

cov1: Covariant[float] = object()
cov2: Covariant[int] = object()
cov1 = cov2  # Ok because int <: float => Covariant[int] <: Covariant[float]
cov2 = cov1  # Invalid

contra1: Contravariant[float] = object()
contra2: Contravariant[int] = object()
contra1 = contra2  # Invalid
contra2 = contra1  # Ok because int <: float => Covariant[float] <: Covariant[int]

inv1: Invariant[float] = object()
inv2: Invariant[int] = object()
inv1 = inv2  # Invalid
inv2 = inv1  # Invalid
