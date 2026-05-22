"""Map presentation constants for Permit Office ArcGIS layers."""

DISPLAY_STATE_SYMBOLS = {
    "stable": ([226, 232, 222, 100], "Stable"),
    "prosperous": ([96, 157, 108, 100], "Prosperous"),
    "restless": ([222, 165, 92, 100], "Restless"),
    "cultured": ([132, 119, 190, 100], "Cultured"),
    "at_risk": ([206, 94, 78, 100], "At Risk"),
    "strained": ([213, 139, 86, 100], "Strained"),
    "aggrieved": ([154, 73, 91, 100], "Aggrieved"),
    "incident": ([209, 58, 58, 100], "Incident"),
    "proposed": ([55, 139, 214, 100], "Proposed"),
    "active": ([47, 145, 99, 100], "Active"),
    "denied": ([120, 120, 120, 100], "Denied"),
    "deferred": ([159, 137, 86, 100], "Deferred"),
    "failed": ([173, 70, 70, 100], "Failed"),
    "settled": ([70, 141, 158, 100], "Settled"),
    "enforced": ([104, 90, 162, 100], "Enforced"),
    "responded": ([74, 130, 181, 100], "Responded"),
    "maintained": ([74, 151, 124, 100], "Maintained"),
    "maintenance_due": ([219, 140, 66, 100], "Maintenance Due"),
    "degraded": ([158, 95, 77, 100], "Degraded"),
    "road": ([100, 100, 100, 100], "Road"),
    "utility": ([67, 127, 190, 100], "Utility"),
    "park": ([97, 160, 100, 100], "Park"),
    "housing": ([193, 136, 101, 100], "Housing"),
    "commerce": ([197, 160, 76, 100], "Commerce"),
    "civic": ([100, 132, 181, 100], "Civic"),
    "industry": ([139, 130, 121, 100], "Industry"),
    "campus": ([138, 113, 176, 100], "Campus"),
    "temporary": ([216, 151, 78, 100], "Temporary"),
    "overlay": ([82, 161, 151, 100], "Overlay"),
    "case": ([201, 88, 101, 100], "Case"),
}

DISTRICT_TYPE_SYMBOLS = {
    "residential": ([194, 137, 98, 100], "Residential"),
    "mercantile": ([207, 166, 71, 100], "Mercantile"),
    "industrial": ([142, 132, 120, 100], "Industrial"),
    "civic": ([92, 132, 184, 100], "Civic"),
    "academic": ([139, 118, 185, 100], "Academic"),
    "natural": ([101, 163, 102, 100], "Natural"),
}

SYMBOLS_BY_FIELD = {
    "display_state": DISPLAY_STATE_SYMBOLS,
    "district_type": DISTRICT_TYPE_SYMBOLS,
}

RENDER_FIELD_BY_LAYER_KEY = {
    "districts": "district_type",
    "points": "display_state",
    "lines": "display_state",
    "zones": "display_state",
}

LAYER_TRANSPARENCY = {
    "districts": 0,
    "points": 0,
    "lines": 0,
    "zones": 70,
}
