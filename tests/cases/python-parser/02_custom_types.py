# type: ignore
# ruff: disable[F821]
from __future__ import annotations

df: Frame[
    location: GeoLocation
]

lat: Column[GeoLocation] = df["location"].lat
lon: Column[GeoLocation] = df["location"].lon

lat + lon

lat1: Latitude = lat[0]
lat2: Latitude = lat[1]
lat_diff: Difference[Latitude] = lat2 - lat1

df2: Frame[
    age: int + (_ >= 0),
    height: float + (_ >= 0),
]
df2_bis: Frame[
    age: int + Positive,
    height: float + Positive,
]
