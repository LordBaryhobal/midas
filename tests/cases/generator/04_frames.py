from typing import Any

from midas import T1, T2, Column, Positive, Positives, cast

o: Any = object()

df1 = cast(T1, o)
df2 = cast(T2, o)

df1 + df2

col1: Positives = df2["c"]
col2 = cast(Column[Positive], col1)
