"""Map presentation constants for Permit Office ArcGIS layers."""

DISPLAY_STATE_SYMBOLS = {
    "stable": ([226, 232, 222, 100], "Stable"),
    "incident": ([206, 54, 52, 100], "Civic Incident"),
    "grievance": ([150, 72, 90, 100], "Local Grievance"),
    "service_gap": ([64, 126, 180, 100], "Service Gap"),
    "hazard": ([196, 90, 74, 100], "Hazard Pressure"),
    "housing_pressure": ([177, 126, 88, 100], "Housing Pressure"),
    "daily_pressure": ([205, 132, 78, 100], "Daily Pressure"),
    "economic_growth": ([106, 162, 114, 100], "Economic Growth"),
    "prosperous": ([106, 162, 114, 100], "Prosperous"),
    "restless": ([216, 159, 84, 100], "Restless"),
    "cultured": ([140, 126, 188, 100], "Cultured"),
    "at_risk": ([196, 90, 74, 100], "At Risk"),
    "strained": ([205, 132, 78, 100], "Strained"),
    "aggrieved": ([150, 72, 90, 100], "Aggrieved"),
    "proposed": ([45, 196, 199, 100], "Proposed"),
    "active": ([52, 150, 100, 100], "Active"),
    "denied": ([112, 112, 112, 100], "Denied"),
    "deferred": ([158, 135, 82, 100], "Deferred"),
    "failed": ([170, 66, 66, 100], "Failed"),
    "settled": ([68, 140, 156, 100], "Settled"),
    "enforced": ([100, 88, 158, 100], "Enforced"),
    "responded": ([70, 128, 178, 100], "Responded"),
    "maintained": ([74, 150, 122, 100], "Maintained"),
    "maintenance_due": ([218, 138, 62, 100], "Maintenance Due"),
    "degraded": ([155, 92, 74, 100], "Degraded"),
    "road": ([58, 62, 60, 100], "Road"),
    "utility": ([54, 126, 185, 100], "Utility"),
    "park": ([82, 150, 88, 100], "Park"),
    "housing": ([177, 126, 88, 100], "Housing"),
    "commerce": ([188, 146, 58, 100], "Commerce"),
    "civic": ([82, 120, 172, 100], "Civic"),
    "industry": ([124, 118, 110, 100], "Industry"),
    "campus": ([130, 112, 174, 100], "Campus"),
    "temporary": ([216, 145, 68, 100], "Temporary"),
    "overlay": ([63, 168, 159, 100], "Overlay"),
    "case": ([199, 82, 96, 100], "Case"),
    "context": ([146, 139, 128, 100], "Context"),
}

DISTRICT_TYPE_SYMBOLS = {
    "residential": ([222, 190, 160, 100], "Residential"),
    "mercantile": ([225, 194, 124, 100], "Mercantile"),
    "industrial": ([174, 166, 154, 100], "Industrial"),
    "civic": ([151, 178, 210, 100], "Civic"),
    "academic": ([176, 160, 211, 100], "Academic"),
    "natural": ([153, 194, 148, 100], "Natural"),
}

IDENTITY_STATE_SYMBOLS = {
    "stable": ([226, 232, 222, 0], "Stable Identity"),
    "vulnerable": ([210, 132, 78, 100], "Vulnerable"),
    "contested": ([188, 74, 70, 100], "Contested Buyout"),
    "converted": ([92, 150, 105, 100], "Recently Converted"),
    "overextended": ([150, 72, 90, 100], "Overextended"),
}

SYMBOLS_BY_FIELD = {
    "display_state": DISPLAY_STATE_SYMBOLS,
    "district_type": DISTRICT_TYPE_SYMBOLS,
    "identity_state": IDENTITY_STATE_SYMBOLS,
}

RENDER_FIELD_BY_LAYER_KEY = {
    "districts": "district_type",
    "points": "display_state",
    "lines": "display_state",
    "zones": "display_state",
}

LAYER_TRANSPARENCY = {
    "districts": 10,
    "points": 0,
    "lines": 0,
    "zones": 35,
}

DISTRICT_OUTLINE_COLOR = [242, 238, 226, 100]
FEATURE_OUTLINE_COLOR = [78, 82, 78, 100]

SYMBOL_STYLE_BY_LAYER = {
    "districts": {
        "outline_color": DISTRICT_OUTLINE_COLOR,
        "outline_width": 3.0,
    },
    "zones": {
        "outline_color": FEATURE_OUTLINE_COLOR,
        "outline_width": 1.1,
    },
    "lines": {
        "outline_color": FEATURE_OUTLINE_COLOR,
        "outline_width": 3.0,
    },
    "points": {
        "outline_color": [245, 241, 231, 100],
        "outline_width": 0.9,
        "size": 9.0,
    },
}


def symbol_style_for(layer_key, value):
    """Return ArcGIS symbol hints for a layer/value pair."""

    style = SYMBOL_STYLE_BY_LAYER.get(layer_key or "", {})
    outline_color = style.get("outline_color", [86, 98, 92, 100])
    outline_width = float(style.get("outline_width", 1.2))
    if value == "proposed":
        outline_color = [31, 220, 222, 100]
        outline_width = max(outline_width, 3.2)
    elif value in ("vulnerable", "contested", "converted", "overextended"):
        outline_color = [93, 48, 48, 100]
        outline_width = max(outline_width, 3.2)
    elif value in ("incident", "failed", "at_risk", "aggrieved", "grievance", "hazard"):
        outline_color = [93, 48, 48, 100]
    elif value in ("road", "utility"):
        outline_width = max(outline_width, 2.8)
    return {
        "outline_color": outline_color,
        "outline_width": outline_width,
        "size": style.get("size"),
    }


def apply_symbol_style(symbol, layer_key, value):
    """Best-effort ArcGIS symbol styling across geometry types."""

    style = symbol_style_for(layer_key, value)
    assignments = [
        ("outlineColor", {"RGB": style["outline_color"]}),
        ("outlineWidth", style["outline_width"]),
        ("width", style["outline_width"]),
    ]
    if style["size"] is not None:
        assignments.append(("size", style["size"]))
    for attr, attr_value in assignments:
        try:
            setattr(symbol, attr, attr_value)
        except Exception:
            pass


def apply_default_symbol_style(symbol, layer_key):
    """Give unique-value renderer fallbacks a visible symbol."""

    fallback = {
        "districts": ([220, 220, 208, 100], [242, 238, 226, 100], 3.0),
        "zones": ([190, 184, 170, 70], [78, 82, 78, 100], 1.1),
        "lines": ([78, 82, 78, 100], [78, 82, 78, 100], 3.0),
        "points": ([78, 82, 78, 100], [245, 241, 231, 100], 0.9),
    }.get(layer_key or "", ([190, 184, 170, 100], [86, 98, 92, 100], 1.2))
    for attr, attr_value in (
        ("color", {"RGB": fallback[0]}),
        ("outlineColor", {"RGB": fallback[1]}),
        ("outlineWidth", fallback[2]),
        ("width", fallback[2]),
    ):
        try:
            setattr(symbol, attr, attr_value)
        except Exception:
            pass
