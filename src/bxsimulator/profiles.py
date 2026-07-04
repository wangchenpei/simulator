"""Built-in defaults for product profiles (YAML overrides)."""

PARTICIPATING_DEFAULTS = {
    "equity_weight": 0.60,
    "bond_weight": 0.40,
    "equity_min": 0.45,
    "equity_max": 0.75,
    "bond_min": 0.25,
    "bond_max": 0.55,
    "smoothing_threshold": 0.065,
}

CI_ANNUITY_DEFAULTS = {
    "equity_weight": 0.25,
    "bond_weight": 0.75,
    "equity_min": 0.15,
    "equity_max": 0.40,
    "bond_min": 0.60,
    "bond_max": 0.85,
    "smoothing_threshold": 0.045,
}
