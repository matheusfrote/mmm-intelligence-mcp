"""Controlled, reproducible DGP for method tests, never business evidence."""

import numpy as np

from .datasets import MEDIA, generate
from .modeling import adstock, design_matrix, hill
from .schemas import GenerateRequest


def controlled_dataset(seed=42, periods=260, noise_sd=10, collinear=False):
    if not 52 <= periods <= 10000 or not 0 <= noise_sd <= 10000:
        raise ValueError("Invalid DGP size or noise")
    data = generate(GenerateRequest(seed=seed, periods=periods))
    rows = data["rows"]
    if collinear:
        for row in rows:
            row[MEDIA[1]] = row[MEDIA[0]]
    cutoff = periods - int(np.ceil(periods * 0.2))
    stocks = [adstock([r[c] for r in rows], 0.5) for c in MEDIA]
    ks = [float(np.median(stock[8:cutoff][stock[8:cutoff] > 0])) for stock in stocks]
    transformed = np.column_stack([hill(s, k) for s, k in zip(stocks, ks)])
    controls = np.array([[r["price_index"], r["promotion"]] for r in rows])
    x = design_matrix(transformed, controls, np.arange(periods), 7)
    coefficients = np.array([9500, 3000, 1800, 0, 200, 500, 100, -2500, 600])
    mean = x @ coefficients
    # Independent seed stream from spend/control generation.
    noise = np.random.default_rng(seed + 2**32).normal(0, noise_sd, periods)
    for i, row in enumerate(rows):
        row["revenue"] = float(mean[i] + noise[i])
    data["source"] = "controlled-dgp-v1"
    data["data_context"]["source_reference"] = "controlled-dgp-v1"
    truth = {
        "known_dgp": True,
        "seed": seed,
        "noise_sd": noise_sd,
        "decay": 0.5,
        "half_saturation": dict(zip(MEDIA, ks)),
        "media_coefficients": dict(zip(MEDIA, coefficients[1:4].tolist())),
        "conditional_mean": mean.tolist(),
        "collinear": collinear,
        "scope": "Matched fixed shapes by construction; recovery does not validate learned shapes or business causality",
    }
    return data, truth
