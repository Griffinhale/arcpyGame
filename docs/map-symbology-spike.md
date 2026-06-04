# Map Symbology Spike

Date: 2026-06-04

## Purpose

Record the current map-rendering strategy for Permit Office and close the broad
symbology spike with explicit evidence and remaining live-observation checks.

## Current Renderer Strategy

- `PermitDistricts` renders by `district_type` by default, preserving the base
  identity of residential, mercantile, industrial, civic, academic, and natural
  districts.
- District labels use `district_name`, not only the stable `cell_id`.
- `identity_state` symbol values exist for stable, vulnerable, contested,
  converted, and overextended states; these remain available for secondary
  renderers or future overlays.
- `PermitPoints`, `PermitLines`, and `PermitZones` render by `display_state`.
  This keeps proposed/active/denied/failed workflow state readable while also
  supporting seeded city-detail classes such as road, utility, housing,
  commerce, civic, industry, campus, and park.
- Proposed features use a high-contrast cyan outline. Roads and utilities get
  line-width hints so they remain visible above districts.
- `PermitZones` retains transparency so district identity is not fully hidden by
  polygon permits or seeded block detail.

## Spike Decision

Do not add a bivariate activity/exposure renderer in this pass. The current
design keeps activity, exposure, services, hazards, housing, and friction visible
through district attributes, filed reports, dashboard pulse text, and
`display_state` pressure overlays. Adding another renderer now would overload
the same visual channels before live ArcGIS evidence shows it is needed.

Do not split support layers into separate family renderers yet. The seeded
city-detail classes already have distinct `display_state` symbol values and
pure tests. Live ArcGIS smoke testing should decide whether that is readable
enough before adding layer-management complexity.

### Buyout legibility update (2026-06-04)

Converted districts are now relabeled with a type-flavored name on conversion
(e.g. "Cinder Yard" -> civic -> "Cinder Hall") in addition to shifting to the
new `district_type` fill color. Combined with the buyout/contested line on the
city news ticker and the named conversion report, this makes district takeovers
legible from the dashboard text and district color/label without activating the
separate `identity_state` (vulnerable/contested/converted) overlay symbols.
Those overlay symbols remain defined in `symbology_config.py` and ready to
activate if a live ArcGIS smoke test shows contested/vulnerable state needs a
dedicated map channel before conversion.

## Verification

Automated checks:

```text
python -m pytest tests/test_permit_office_symbology.py tests/test_permit_office_arcgis_geometry.py -q
```

Expected coverage:

- district layers render by `district_type`,
- district labels use `district_name`,
- support layers render by `display_state`,
- support symbol values include road, utility, park, housing, commerce, civic,
  industry, campus, proposed, active, maintenance due, and degraded,
- roads/utilities and proposed features have readable style hints,
- layer order keeps districts as the base and lines on top.

## Live ArcGIS Observation Checklist

Record screenshots or notes for:

- district identity readability at normal demo zoom,
- vulnerable, contested, and converted district readability when present,
- proposed vs active feature visibility,
- road and utility line distinction,
- seeded housing/business/civic/industrial/campus/park detail readability,
- whether `PermitZones` transparency preserves district identity,
- whether any activity/exposure/risk concept is still unclear enough to justify
  a new renderer.
