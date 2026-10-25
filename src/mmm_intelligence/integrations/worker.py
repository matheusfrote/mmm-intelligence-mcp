"""Standalone worker. Imported only by the backend's own Python environment.

Arguments/paths originate in the host bridge, never directly in MCP input.
Native models are serialized by official safe formats, embedded in hashed JSON.
"""

import base64
import json
import os
import subprocess
import sys
import traceback
from importlib.metadata import version
from pathlib import Path


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


def summarize(samples, dates, observed=None):
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
        "r_hat_max": float(statistics["r_hat"].max()),
        "ess_bulk_min": float(statistics["ess_bulk"].min()),
        "method": "ArviZ rank-normalized split R-hat and bulk ESS",
        "convergence_certified": False,
    }


def pymc(payload, root):
    import numpy as np
    import pandas as pd
    from pymc_marketing.mmm.components.adstock import GeometricAdstock
    from pymc_marketing.mmm.components.saturation import LogisticSaturation
    from pymc_marketing.mmm.mmm import MMM

    native = root / "model.nc"
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
        if not np.allclose(before, after, rtol=1e-7, atol=1e-7):
            raise ValueError("PyMC persistence changed predictions")
        # Current ArviZ exposes DataTree diagnostics through xarray accessors.
        idata = model.idata
        divergences = None
        try:
            divergences = int(idata["sample_stats"]["diverging"].sum().item())
        except (KeyError, AttributeError):
            pass
        return {
            "backend": "pymc_marketing",
            "backend_version": version("pymc-marketing"),
            "native_format": "netcdf-h5netcdf",
            "native_base64": base64.b64encode(native.read_bytes()).decode(),
            "dataset": dataset,
            "request": req,
            "cutoff": cutoff,
            "restore_verified": True,
            "test": summarize(before, dates[cutoff:], y.iloc[cutoff:].to_numpy()),
            "diagnostics": {
                **pymc_diagnostics(model),
                "divergences": divergences,
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
    if "y_original_scale" not in model.model.named_vars:
        model.add_original_scale_contribution_variable(var=["y"])
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
            np.asarray(pp["y_original_scale"]), df[req["date_column"]].iloc[cutoff:].tolist()
        ),
        "exploratory": True,
        "warnings": ["Conditional historical scenario; not a causal intervention estimate"],
    }


def meridian(payload, root):
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
        df = pd.DataFrame(dataset["rows"])
        cutoff = len(df) - int(np.ceil(len(df) * req["test_fraction"]))
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
        if not np.allclose(before, after, rtol=1e-6, atol=1e-6):
            raise ValueError("Meridian persistence changed expected outcomes")
        diagnostics = {
            "chains": req["chains"],
            "draws": req["draws"],
            "convergence_certified": False,
        }
        try:
            import arviz as az

            summary = az.summary(fitted.inference_data, kind="diagnostics")
            diagnostics.update(
                r_hat_max=float(summary["r_hat"].max()),
                ess_bulk_min=float(summary["ess_bulk"].min()),
            )
        except (ValueError, KeyError, TypeError):
            diagnostics["summary_available"] = False
        return {
            "backend": "google_meridian",
            "backend_version": version("google-meridian"),
            "native_format": "protobuf-binpb",
            "native_base64": base64.b64encode(native.read_bytes()).decode(),
            "dataset": dataset,
            "request": req,
            "cutoff": cutoff,
            "restore_verified": True,
            "test": summarize(
                before[:, cutoff:],
                df[req["date_column"]].iloc[cutoff:].tolist(),
                df[req["target_column"]].iloc[cutoff:].to_numpy(),
            ),
            "diagnostics": diagnostics,
            "warnings": [
                "SHORT_CHAINS: functional test does not establish convergence",
                "SPEND_PROXY: synthetic spend used as exposure proxy",
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
        ),
        "warnings": [
            "Meridian future forecasting is not exposed; historical scenario only",
            "No demonstrated causal attribution",
        ],
    }


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
            project = Path(__file__).resolve().parents[3]
            default = project / "var/runtime/r-portable/R-4.5.2/bin/Rscript.exe"
            rscript = Path(os.environ.get("MMM_RSCRIPT", str(default)))
            if not rscript.is_file():
                raise FileNotFoundError("Configured Rscript runtime is unavailable")
            r_result = root / "r-result.json"
            subprocess.run(
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
