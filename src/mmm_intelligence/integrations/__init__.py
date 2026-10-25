"""Implemented adapters; runtime availability and statistical validity are separate."""

CAPABILITIES = {
    "google_meridian": "implemented_optional_runtime",
    "meta_robyn": "implemented_optional_runtime",
    "pymc_marketing": "implemented_optional_runtime",
    "investment_optimization": "implemented_local",
    "analytical_dashboards": "implemented_local",
    "automated_reports": "implemented_local",
}

# Compatibility name retained for clients which imported the initial registry.
PLANNED_CAPABILITIES: dict[str, str] = {}
