# type: ignore
# ruff: disable[F821]
from __future__ import annotations

# A data-frame using a custom type
df: Frame[
    location: GeoLocation
]

# Properties of a type can be used on a column of that type
lat: Column[GeoLocation] = df["location"].lat
lon: Column[GeoLocation] = df["location"].lon

# Unregistered operations between types are not permitted
lat + lon  # Invalid operation

# Registered operations are permitted
lat1: Latitude = lat[0]
lat2: Latitude = lat[1]
lat_diff: Difference[Latitude] = lat2 - lat1  # Valid operation

# In addition to the type, a column can have one or more constraints, either defined inline or in a separate file
df2: Frame[
    age: int + (_ >= 0),
    height: float + (_ >= 0),
]
df2_bis: Frame[
    age: int + Positive,
    height: float + Positive,
]
