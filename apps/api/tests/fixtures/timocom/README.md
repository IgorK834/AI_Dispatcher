# TIMOCOM source fixtures — O-4 / FEAT-002

The owner requested O-4 end to end in the coding-agent chat on 2026-11-11,
authorising one fetch of the public export and recording the decision in
[issue #4](https://github.com/IgorK834/AI_Dispatcher/issues/4).

Source: [official Freight Exchange reference](https://developer.timocom.com/docs/freight-exchange/bbf3f610ba4d2-freight-exchange)
and its [OpenAPI export](https://api.stoplight.io/projects/cHJqOjIwMTI4Nw/branches/v3/export/reference/openapi.yaml),
accessed 2026-11-11. The API version (`info.version`) is **3.0.6**; the
OpenAPI document format (`openapi`) is **3.0.3**.

Only the needed example subsets and two documented values are stored here.
The complete export is excluded; its redistribution licence was not established
(`info.license` is absent). Each JSON file includes `_source` with its URL,
versions, access date, source pointer and document SHA-256. `example` contains
the extracted data; `_source` is local metadata, never a TIMOCOM payload field.
Tests read these committed files offline; they must not download the export.

| File | Source and intended use |
|---|---|
| `find_freight_offers.json` | Search-response example projected onto FEAT-002 FR-8 fields; `HH:MM` times. |
| `lookup_freight_offers.json` | Lookup-response example projected onto the same fields; preserves `"creationDateTime "`, distance 4711 km, null coordinates and day-only windows. |
| `loading_places.json` | Unchanged official pickup/delivery examples with `HH:MM:SSZ` times and coordinates. |
| `vehicle_values.json` | `REFRIGERATOR` for `vehicleProperties.body[]`; `TAIL_LIFT` for `vehicleProperties.equipment[]` (OQ-002-02). |

The two vehicle values are listed in schema descriptions, not machine-readable
`enum` arrays. Use `["REFRIGERATOR"]` for `INCOMPATIBLE_BODY` and `["TAIL_LIFT"]`
for `INCOMPATIBLE_EQUIPMENT`. Omit `customer` from generated mock offers as agreed
in OQ-002-02. Neither `customer` nor `contactPerson` is retained in these fixtures.
These are documentation examples for contract tests, not live exchange offers
or generated demo data; do not import them as demo seed data.

The official response examples contain invalid stop types: both search stops
are `LOADING`, and both lookup stop types are null. The lookup example also has
a null delivery `latestLoadingDate`. Retained values are unchanged. Under
FEAT-002 FR-20, the original response examples are mapping failures; they are
not successful mapper inputs. Slice 002/3 must explicitly record any changes
when deriving valid offer inputs for AC-FEAT-002-09 and its tolerance tests.
The separate loading-place examples provide valid pickup/delivery types and
the alternate time format without changing the source response snapshots.

O-4 supplies source material only. Mapper behaviour (AC-FEAT-002-09–12),
generator difficulty counts (AC-FEAT-002-06), and their tests remain the work of
slices 002/3 and 002/2 respectively.
