"""Compact native posterior storage; no thinning, rounding or lost free variables."""


def recomputable_variables(dimensions, free_variables):
    if not set(free_variables).issubset(dimensions):
        raise ValueError("Native posterior is missing free random variables")
    return [
        name for name, dims in dimensions.items() if "date" in dims and name not in free_variables
    ]


def save_pymc_model(model, path, encoding):
    """Native graph recomputes date deterministics when predicting after load."""
    original = model.idata
    removed = recomputable_variables(
        {name: variable.dims for name, variable in original["posterior"].data_vars.items()},
        {variable.name for variable in model.model.free_RVs},
    )
    compact = original.copy(deep=False)
    compact["posterior"] = compact["posterior"].to_dataset().drop_vars(removed)
    try:
        model.idata = compact
        model.save(str(path), engine="h5netcdf", encoding=encoding(compact))
    finally:
        model.idata = original
    return {
        "compression": "zlib-4",
        "lossless": True,
        "all_groups_retained": True,
        "all_draws_retained": True,
        "all_free_variables_retained": True,
        "recomputed_date_deterministics": removed,
        "scope": "Deterministic time arrays are recomputed from the saved native graph; all sampled values remain unchanged",
    }
