# Geodesic Distance

`geodesic_distance` calculates the straight-line distance between two latitude/longitude points using the Haversine formula.

## Inputs

- `lat_a`, `lon_a`: latitude and longitude of point A
- `lat_b`, `lon_b`: latitude and longitude of point B
- `resolve_addresses`: optionally resolve both points to addresses with OpenStreetMap Nominatim
- `language`: optional language for address resolution

## Output

The tool returns `distance_km`, `distance_m`, the initial bearing, and the calculation method. Address resolution is optional and is not needed when coordinates are already known.

This is a straight-line geographic distance, not a road or public-transit route distance. Nominatim requests are subject to OpenStreetMap usage policies and rate limits.
