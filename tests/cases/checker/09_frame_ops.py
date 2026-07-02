# type: ignore
# ruff: disable [F821]

df1: Frame[a:int, b:float]
df2: Frame[a:int, b:float]

_: Any

# Arithmetic
_ = df1 + df2
_ = df1 - df2
_ = df1 * df2
_ = df1 / df2
_ = df1 // df2
_ = df1 % df2
_ = df1**df2

# Comparisons
_ = df1 < df2
_ = df1 > df2
_ = df1 <= df2
_ = df1 >= df2
_ = df1 != df2
_ = df1 == df2

# Statistical
_ = df1.kurt()
_ = df1.kurtosis()
_ = df1.max()
_ = df1.mean()
_ = df1.median()
_ = df1.min()
_ = df1.mode()
_ = df1.prod()
_ = df1.product()
_ = df1.std()
_ = df1.sum()
_ = df1.var()
