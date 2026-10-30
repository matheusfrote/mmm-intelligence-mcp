"""Standalone worker. Imported only by the backend's own Python environment.

Arguments/paths originate in the host bridge, never directly in MCP input.
Native models are serialized by official safe formats, embedded in hashed JSON.
"""

import base64
import json
import math
import os

# R worker is fixed; its runtime is selected only by the host.
import subprocess  # nosec B404
import sys
import traceback
from importlib.metadata import version
from pathlib import Path


def declared_target_type(dataset, target_column):
    """Use declared KPI semantics; support only the known legacy demo inference."""
    target_type = dataset.get("target_type", "unspecified")
    if not isinstance(target_type, str) or target_type not in {
        "revenue",
        "non_revenue",
        "unspecified",
    }:
        raise ValueError("Invalid dataset target_type")
    if (
        target_type == "unspecified"
        and dataset.get("synthetic") is True
        and dataset.get("source") == "built-in-demo-v1"
        and target_column == "revenue"
    ):
        return "revenue"
    return target_type


def prepare_meridian_holdout(dataset, request):
    """Isolate holdout targets before native preprocessing, without importing TF.

    Meridian 2.1 masks likelihood observations after fitting its KPI scaler to
    the complete input. Train-only placeholders prevent the withheld observed
    target from affecting that scaler. This is not a train-prefix-only scaler.
    """
    if declared_target_type(dataset, request["target_column"]) != "revenue":
        raise ValueError("Meridian adapter requires explicitly declared revenue target_type")
    rows = dataset.get("rows")
    fraction = request.get("test_fraction")
    if (
        not isinstance(rows, list)
        or len(rows) < 2
        or isinstance(fraction, bool)
        or not isinstance(fraction, (int, float))
        or not math.isfinite(fraction)
        or not 0 < fraction < 1
    ):
        raise ValueError("Invalid Meridian holdout shape or test_fraction")
    cutoff = len(rows) - math.ceil(len(rows) * fraction)
    if not 1 < cutoff < len(rows):
        raise ValueError("Meridian holdout needs at least two train and one test observation")
    observed = []
    for row in rows:
        value = row.get(request["target_column"]) if isinstance(row, dict) else None
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError("Meridian targets must be finite nonnegative numbers")
        observed.append(float(value))
    try:
        placeholder = math.fsum(observed[:cutoff]) / cutoff
    except OverflowError as exc:
        raise ValueError("Meridian train-only placeholder exceeds floating-point range") from exc
    model_rows = [dict(row) for row in rows]
    for row in model_rows[cutoff:]:
        row[request["target_column"]] = placeholder
    return (
        model_rows,
        observed,
        cutoff,
        {
            "policy": "holdout_target_replaced_with_train_mean_before_native_loader",
            "placeholder": placeholder,
            "train_rows": cutoff,
            "test_rows": len(rows) - cutoff,
            "target_holdout_used_in_native_preprocessing": False,
            "native_scaler_scope": "training_targets_and_train_only_holdout_placeholders",
            "likelihood_exclusion": "native_HoldoutSpec",
        },
    )


def robyn_split_indices(n, train_size=0.6):
    """Reference of R 3.12.1's type-7 quantile split; zero-based bounds."""
    if (
        isinstance(n, bool)
        or not isinstance(n, int)
        or n < 3
        or isinstance(train_size, bool)
        or not isinstance(train_size, (int, float))
        or not math.isfinite(train_size)
        or not 0 < train_size < 1
    ):
        raise ValueError("Invalid native Robyn split")
    train_end = math.floor(1 + (n - 1) * train_size)
    validation_end = train_end + math.floor(((1 - train_size) / 2) * n)
    if not 0 < train_end < validation_end < n:
        raise ValueError("Robyn split has an empty partition")
    return {"train_end": train_end, "validation_end": validation_end, "test_end": n}


def summarize_diagnostics(statistics):
    """Keep unrounded finite extrema and explicitly count undefined diagnostics."""
    result = {"convergence_certified": False}
    for column, name, aggregate in (
        ("r_hat", "r_hat_max", max),
        ("ess_bulk", "ess_bulk_min", min),
        ("ess_tail", "ess_tail_min", min),
    ):
        values = [float(value) for value in statistics[column]] if column in statistics else []
        finite = [value for value in values if math.isfinite(value)]
        result[name] = aggregate(finite) if finite else None
        result[column + "_available"] = bool(finite)
        result[column + "_undefined_count"] = len(values) - len(finite)
    return result


def divergence_diagnostics(idata):
    try:
        return {
            "divergences": int(idata["sample_stats"]["diverging"].sum().item()),
            "divergences_available": True,
        }
    except (KeyError, AttributeError, TypeError):
        return {
            "divergences": None,
            "divergences_available": False,
            "divergences_unavailable_reason": "sample_stats.diverging is absent",
        }


def finite_json(value):
    import math

    if isinstance(value, dict):
        return {str(k): finite_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite_json(v) for v in value]
    if hasattr(value, "tolist"):
        return finite_json(value.tolist())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def summarize(samples, dates, observed=None, interval_type="unspecified"):
    import numpy as np

    draws = np.asarray(samples, float).reshape(-1, len(dates))
    if not np.isfinite(draws).all():
        raise ValueError("Nonfinite backend predictions")
    mean = draws.mean(axis=0)
    result = {
        "dates": dates,
        "mean": mean.tolist(),
        "lower_90": np.quantile(draws, 0.05, axis=0).tolist(),
        "upper_90": np.quantile(draws, 0.95, axis=0).tolist(),
        "samples": draws.shape[0],
        "interval_type": interval_type,
        "interval_level": 0.9,
    }
    if observed is not None:
        y = np.asarray(observed, float)
        residual = y - mean
        variance = np.sum((y - y.mean()) ** 2)
        result["metrics"] = {
            "mae": float(np.abs(residual).mean()),
            "wape_percent": float(100 * np.abs(residual).sum() / np.abs(y).sum())
            if np.abs(y).sum()
            else None,
            "r2": float(1 - np.sum(residual**2) / variance) if variance else None,
        }
    return result


def pymc_diagnostics(model):
    from arviz_stats import summary

    names = [
        name for name, var in model.idata["posterior"].data_vars.items() if "date" not in var.dims
    ]
    statistics = summary(model.idata, var_names=names, kind="diagnostics", round_to="none")
    return {
        **summarize_diagnostics(statistics),
        "method": "ArviZ rank-normalized split R-hat, bulk ESS and tail ESS",
        "summarized_variables": names,
        "excluded_date_dependent_variables": [
            name for name in model.idata["posterior"].data_vars if name not in names
        ],
        "convergence_certified": False,
    }


def pymc_effective_configuration(model, target_type):
    from pymc_marketing.serialization import serialization

    return {
        "prior_source": "package_defaults_no_custom_priors",
        "model_config": serialization.serialize_model_config(model.model_config),
        "adstock": serialization.serialize(model.adstock),
        "saturation": serialization.serialize(model.saturation),
        "target_type": target_type,
        "interval_type": "posterior_predictive_observed",
    }


def meridian_effective_configuration(model):
    from google.protobuf.json_format import MessageToDict
    from meridian.schema.serde import distribution, function_registry

    serde = distribution.DistributionSerde(function_registry.FunctionRegistry())
    return {
        "prior_source": "package_defaults_no_custom_priors",
        "configured_priors": MessageToDict(serde.serialize(model.model_spec.prior)),
        "effective_broadcast_priors": MessageToDict(serde.serialize(model.prior_broadcast)),
        "media_prior_type": model.model_spec.media_prior_type,
        "target_type": "revenue",
        "interval_type": "conditional_expected_outcome",
    }


def ensure_original_scale(model):
    """Compatibility boundary for native models saved without this optional variable."""
    if "y_original_scale" not in model.model.named_vars:
        model.add_original_scale_contribution_variable(var=["y"])


def verify_restoration(before, after, backend, tolerance):
    import numpy as np

    if not np.allclose(before, after, rtol=tolerance, atol=tolerance):
        raise ValueError(backend + " persistence changed predictions")


def meridian_diagnostics(inference_data, request):
    import arviz as az

    diagnostics = {}
    diagnostics.update(
        chains=request["chains"],
        draws=request["draws"],
        tune=request["tune"],
        convergence_certified=False,
    )
    try:
        summary = az.summary(inference_data, kind="diagnostics", round_to="none")
        diagnostics.update(summarize_diagnostics(summary))
        diagnostics["summary_available"] = True
    except (ValueError, KeyError, TypeError):
        diagnostics.update(summarize_diagnostics({}))
        diagnostics["summary_available"] = False
        diagnostics["summary_unavailable_reason"] = "ArviZ diagnostic summary unavailable"
    diagnostics.update(divergence_diagnostics(inference_data))
    return diagnostics


def pymc(payload, root):
    import numpy as np
    import pandas as pd
    from pymc_marketing.mmm.components.adstock import GeometricAdstock
    from pymc_marketing.mmm.components.saturation import LogisticSaturation
    from pymc_marketing.mmm.mmm import MMM

    native = root / "model.nc"
    if payload["operation"] == "forecast":
        stored = payload["model"]
        req = stored["request"]
        future = payload["future_rows"]
        combined = pd.DataFrame(pymc_future_rows(stored, future))
        combined[req["date_column"]] = pd.to_datetime(combined[req["date_column"]])
        native.write_bytes(base64.b64decode(stored["native_base64"], validate=True))
        model = MMM.load(str(native))
        ensure_original_scale(model)
        pp = model.sample_posterior_predictive(
            X=combined,
            extend_idata=False,
            combined=False,
            include_last_observations=True,
            random_seed=req["seed"],
            progressbar=False,
            var_names=["y_original_scale"],
        )
        samples = np.asarray(pp["y_original_scale"]).reshape(-1, len(combined))[:, -len(future) :]
        result = summarize(
            samples,
            [r[req["date_column"]] for r in future],
            interval_type="posterior_predictive_observed",
        )
        result.update(
            total_mean=float(samples.sum(axis=1).mean()),
            total_interval_90=np.quantile(samples.sum(axis=1), [0.05, 0.95]).tolist(),
        )
        return {
            "prediction": result,
            "backend": "pymc_marketing",
            "scope": "future_conditional_projection",
            "refit": False,
        }
    if payload["operation"] == "train":
        req = payload["request"]
        dataset = payload["dataset"]
        df = pd.DataFrame(dataset["rows"])
        dates = df[req["date_column"]].tolist()
        df[req["date_column"]] = pd.to_datetime(df[req["date_column"]])
        cutoff = len(df) - int(np.ceil(len(df) * req["test_fraction"]))
        x = df[[req["date_column"], *req["media_columns"], *req["control_columns"]]].copy()
        model = MMM(
            date_column=req["date_column"],
            target_column=req["target_column"],
            channel_columns=req["media_columns"],
            control_columns=req["control_columns"] or None,
            adstock=GeometricAdstock(l_max=8),
            saturation=LogisticSaturation(),
            yearly_seasonality=1,
        )
        y = df[req["target_column"]].copy()
        model.fit(
            X=x.iloc[:cutoff],
            y=y.iloc[:cutoff],
            chains=req["chains"],
            cores=1,
            draws=req["draws"],
            tune=req["tune"],
            random_seed=req["seed"],
            progressbar=False,
            compute_convergence_checks=True,
        )
        model.add_original_scale_contribution_variable(var=["y"])

        def prediction(fitted):
            pp = fitted.sample_posterior_predictive(
                X=x.iloc[cutoff:],
                extend_idata=False,
                combined=False,
                include_last_observations=True,
                random_seed=req["seed"],
                progressbar=False,
                var_names=["y_original_scale"],
            )
            return np.asarray(pp["y_original_scale"]).reshape(-1, len(x) - cutoff)

        before = prediction(model)
        model.save(str(native), engine="h5netcdf")
        restored = MMM.load(str(native))
        after = prediction(restored)
        verify_restoration(before, after, "PyMC", 1e-7)
        # Current ArviZ exposes DataTree diagnostics through xarray accessors.
        idata = model.idata
        return {
            "backend": "pymc_marketing",
            "backend_version": version("pymc-marketing"),
            "native_format": "netcdf-h5netcdf",
            "native_base64": base64.b64encode(native.read_bytes()).decode(),
            "dataset": dataset,
            "request": req,
            "cutoff": cutoff,
            "restore_verified": True,
            "effective_configuration": pymc_effective_configuration(
                model, declared_target_type(dataset, req["target_column"])
            ),
            "test": summarize(
                before,
                dates[cutoff:],
                y.iloc[cutoff:].to_numpy(),
                interval_type="posterior_predictive_observed",
            ),
            "diagnostics": {
                **pymc_diagnostics(model),
                **divergence_diagnostics(idata),
                "chains": req["chains"],
                "draws": req["draws"],
                "tune": req["tune"],
                "convergence_certified": False,
            },
            "warnings": [
                "FUNCTIONAL_SAMPLING_ONLY: inspect R-hat/ESS/divergences before statistical use",
                "Predictive intervals are conditional on model assumptions; no causal guarantee",
            ],
        }
    stored = payload["model"]
    req = stored["request"]
    df = pd.DataFrame(stored["dataset"]["rows"])
    x = df[[req["date_column"], *req["media_columns"], *req["control_columns"]]].copy()
    x[req["date_column"]] = pd.to_datetime(x[req["date_column"]])
    mult = payload["request"]["media_multiplier"]
    if set(mult) - set(req["media_columns"]):
        raise ValueError("Unknown media scenario channels")
    cutoff = stored["cutoff"]
    for c, factor in mult.items():
        x.loc[cutoff:, c] = x.loc[cutoff:, c] * factor
    native.write_bytes(base64.b64decode(stored["native_base64"], validate=True))
    model = MMM.load(str(native))
    ensure_original_scale(model)
    pp = model.sample_posterior_predictive(
        X=x.iloc[cutoff:],
        extend_idata=False,
        combined=False,
        include_last_observations=True,
        random_seed=req["seed"],
        progressbar=False,
        var_names=["y_original_scale"],
    )
    return {
        "backend": "pymc_marketing",
        "model_id": stored["model_id"],
        "scope": "historical_holdout_scenario",
        "diagnostics": pymc_diagnostics(model),
        "prediction": summarize(
            np.asarray(pp["y_original_scale"]),
            df[req["date_column"]].iloc[cutoff:].tolist(),
            interval_type="posterior_predictive_observed",
        ),
        "exploratory": True,
        "warnings": ["Conditional historical scenario; not a causal intervention estimate"],
    }


def meridian(payload, root):
    if payload["operation"] == "train":
        model_rows, observed, cutoff, holdout_policy = prepare_meridian_holdout(
            payload["dataset"], payload["request"]
        )
    import numpy as np
    import pandas as pd
    from meridian.analysis import analyzer
    from meridian.data import load
    from meridian.model import model as model_module
    from meridian.model import spec
    from meridian.schema.serde import meridian_serde

    native = root / "model.binpb"
    if payload["operation"] == "train":
        req = payload["request"]
        dataset = payload["dataset"]
        df = pd.DataFrame(model_rows)
        # Spend is an explicitly declared proxy for exposure in this synthetic adapter.
        exposure = []
        for c in req["media_columns"]:
            name = "exposure_" + c
            df[name] = df[c]
            exposure.append(name)
        mapping = load.CoordToColumns(
            time=req["date_column"],
            kpi=req["target_column"],
            controls=req["control_columns"] or None,
            media=exposure,
            media_spend=req["media_columns"],
        )
        data = load.DataFrameDataLoader(
            df=df,
            coord_to_columns=mapping,
            kpi_type="revenue",
            media_to_channel=dict(zip(exposure, req["media_columns"])),
            media_spend_to_channel={c: c for c in req["media_columns"]},
        ).load()
        holdout = spec.HoldoutSpec(spec=[spec.DateRange(df[req["date_column"]].iloc[cutoff], None)])
        fitted = model_module.Meridian(
            input_data=data, model_spec=spec.ModelSpec(max_lag=8, knots=4, holdout=holdout)
        )
        fitted.sample_prior(n_draws=req["draws"], seed=req["seed"])
        fitted.sample_posterior(
            n_chains=req["chains"],
            n_adapt=req["tune"],
            n_burnin=req["tune"],
            n_keep=req["draws"],
            seed=req["seed"],
            max_tree_depth=8,
        )

        def prediction(m):
            return np.asarray(
                analyzer.Analyzer(m).expected_outcome(
                    aggregate_geos=True, aggregate_times=False, use_kpi=True
                )
            ).reshape(-1, len(df))

        before = prediction(fitted)
        meridian_serde.save_meridian(fitted, str(native))
        restored = meridian_serde.load_meridian(str(native))
        after = prediction(restored)
        verify_restoration(before, after, "Meridian", 1e-6)
        diagnostics = meridian_diagnostics(fitted.inference_data, req)
        return {
            "backend": "google_meridian",
            "backend_version": version("google-meridian"),
            "native_format": "protobuf-binpb",
            "native_base64": base64.b64encode(native.read_bytes()).decode(),
            "dataset": dataset,
            "request": req,
            "cutoff": cutoff,
            "restore_verified": True,
            "holdout_policy": holdout_policy,
            "effective_configuration": meridian_effective_configuration(fitted),
            "test": summarize(
                before[:, cutoff:],
                df[req["date_column"]].iloc[cutoff:].tolist(),
                observed[cutoff:],
                interval_type="conditional_expected_outcome",
            ),
            "diagnostics": diagnostics,
            "warnings": [
                "SHORT_CHAINS: functional test does not establish convergence",
                "SPEND_PROXY: synthetic spend used as exposure proxy",
                "Holdout target uses train-only placeholders in native preprocessing",
                "No demonstrated causal attribution",
            ],
        }
    stored = payload["model"]
    req = stored["request"]
    native.write_bytes(base64.b64decode(stored["native_base64"], validate=True))
    fitted = meridian_serde.load_meridian(str(native))
    multiplier = payload["request"]["media_multiplier"]
    if multiplier:
        from meridian.analysis import tensors

        media = np.array(fitted.input_data.media.values, copy=True)
        channels = req["media_columns"]
        if set(multiplier) - set(channels):
            raise ValueError("Unknown media scenario channels")
        for name, factor in multiplier.items():
            media[:, :, channels.index(name)] *= factor
        new_data = tensors.DataTensors(media=media)
    else:
        new_data = None
    out = np.asarray(
        analyzer.Analyzer(fitted).expected_outcome(
            new_data=new_data, aggregate_geos=True, aggregate_times=False, use_kpi=True
        )
    )
    n = len(stored["dataset"]["rows"])
    cutoff = stored["cutoff"]
    return {
        "backend": "google_meridian",
        "model_id": stored["model_id"],
        "scope": "historical_scenario_same_dimensions",
        "exploratory": True,
        "prediction": summarize(
            out.reshape(-1, n)[:, cutoff:],
            [r[req["date_column"]] for r in stored["dataset"]["rows"]][cutoff:],
            interval_type="conditional_expected_outcome",
        ),
        "warnings": [
            "Meridian future forecasting is not exposed; historical scenario only",
            "No demonstrated causal attribution",
        ],
    }


def pymc_future_rows(stored, future_rows):
    """Bridge the full post-training gap so future adstock does not skip holdout media."""
    req = stored["request"]
    columns = [req["date_column"], *req["media_columns"], *req["control_columns"]]
    return [
        {c: r[c] for c in columns}
        for r in [*stored["dataset"]["rows"][stored["cutoff"] :], *future_rows]
    ]


def main():
    backend, source, destination = sys.argv[1:]
    try:
        payload = json.loads(Path(source).read_text(encoding="utf-8"))
        if backend == "google_meridian":
            result = meridian(payload, Path(destination).parent)
        elif backend == "pymc_marketing":
            result = pymc(payload, Path(destination).parent)
        else:
            root = Path(destination).parent
            if payload["operation"] == "train":
                target_type = declared_target_type(
                    payload["dataset"], payload["request"]["target_column"]
                )
                if target_type == "unspecified":
                    raise ValueError("Robyn requires declared revenue or non_revenue target_type")
            project = Path(__file__).resolve().parents[3]
            default = project / "var/runtime/r-portable/R-4.5.2/bin/Rscript.exe"
            rscript = Path(os.environ.get("MMM_RSCRIPT", str(default)))
            if not rscript.is_file():
                raise FileNotFoundError("Configured Rscript runtime is unavailable")
            r_result = root / "r-result.json"
            # Fixed argv, shell=False; runtime from trusted host configuration.
            subprocess.run(  # nosec B603
                [
                    str(rscript),
                    "--vanilla",
                    str(Path(__file__).with_name("robyn_worker.R")),
                    source,
                    str(r_result),
                ],
                check=True,
                timeout=850,
            )
            result = json.loads(r_result.read_text(encoding="utf-8"))
            if payload["operation"] == "train":
                native = root / "model.robyn.json"
                result.update(
                    native_format="robyn-json",
                    native_base64=base64.b64encode(native.read_bytes()).decode(),
                    dataset=payload["dataset"],
                    request=payload["request"],
                )
        if isinstance(result.get("warnings"), str):
            result["warnings"] = [result["warnings"]]
        response = {"ok": True, "data": finite_json(result)}
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        response = {
            "ok": False,
            "code": "BACKEND_FAILED",
            "message": (
                "R worker failed; inspect the private backend diagnostic log"
                if isinstance(exc, subprocess.CalledProcessError)
                else type(exc).__name__
                + ": "
                + str(exc)
                .replace(str(Path(destination).parent), "<job>")
                .replace(str(Path.home()), "<home>")[:500]
            ),
        }
    Path(destination).write_text(json.dumps(response, allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    main()
