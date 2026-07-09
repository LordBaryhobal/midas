# type: ignore
# ruff: disable[F821]
from __future__ import annotations

# A data-frame using a custom type
df: Frame[
    location: GeoLocation
]

# Properties of a type can be used on a column of that type
lat: Column[Latitude] = ...
lon: Column[Longitude] = ...

# Unregistered operations between types are not permitted
lat + lon  # Invalid operation

# Registered operations are permitted
lat1: Latitude = lat[0]
lat2: Latitude = lat[1]
lat_diff: Difference[Latitude] = lat2 - lat1  # Valid operation
