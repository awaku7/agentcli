# Public Transit Route Search

`public_transit_route` searches Japanese train, bus, airline, ferry, and other public-transit routes using Yahoo! Japan Transit.

## Inputs

- `origin`: station, bus stop, address, or facility. Ambiguous names such as `郡山` may be resolved from the destination region (for example, `堺筋本町` selects `郡山(奈良県)`).
- `destination`: station, bus stop, address, or facility
- `departure`: optional local ISO 8601 date/time
- `max_routes`: 1–6 candidate routes (default 3)
- `sort_by`: `recommended`, `fastest`, `cheapest`, or `fewest_transfers`
- `ticket`: `ic` or `normal`
- `avoid`: `shinkansen`, `limited_express`, `airline`, `highway_bus`, `local_bus`, or `ship`

## Output

Each candidate includes departure/arrival times, duration, transfer count, fare in yen, fare detail, distance, segments, and an itinerary. The `fare_breakdown` field reports the payment units separately when Yahoo! provides enough information to identify them—for example, a JR fare and an Osaka Metro fare—with `operator`, `unit`, `label`, and `amount_yen` for each item. `fare_yen` is the total shown for the candidate. The response also includes the Yahoo! Japan Transit source URL, a Markdown `source_link` that preserves the search query, retrieval time, and `fare_type: web_checked`.

For example, a route from 郡山 (Nara) to 堺筋本町 may contain separate JR and Osaka Metro payment items. The breakdown is informational and follows Yahoo! Japan Transit’s fare presentation; it does not perform payment or guarantee that a single ticket covers all segments.

The route and fare information is supplied by Yahoo! Japan Transit and may change. Confirm the result before making a time-sensitive journey.

## Availability and usage

Ambiguous station resolution uses a bundled station master generated from MLIT’s N02 railway data (2024). Source and terms-of-use information are recorded in `src/uagent/tools/data/jp_stations.meta.json`. The master may not reflect the latest railway network, so verify the final station and route in Yahoo! Japan Transit.

The tool requires network access and uses the public Yahoo! Japan Transit web result. Use it responsibly and comply with Yahoo!/LY Corporation terms, robots rules, rate limits, and attribution requirements. It is not an official Yahoo API client.
