"""Portable canonical exports without filesystem or network side effects."""

import csv
import io
import json


def export(analysis, format):
    if format == "json":
        content = json.dumps(analysis, ensure_ascii=False, indent=2, allow_nan=False)
    elif format == "csv":
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=["date", "observed", "predicted", "residual"])
        writer.writeheader()
        for p in analysis["evaluation"]:
            writer.writerow(
                {k: p[k] for k in ("date", "observed", "predicted")}
                | {"residual": p["observed"] - p["predicted"]}
            )
        content = stream.getvalue()
    else:
        content = "\n".join(
            [
                "# Análise MMM exploratória",
                "",
                f"Motor: {analysis['backend']}; modelo: {analysis['model_id']}",
                "Sem demonstração causal; nenhuma recomendação de investimento autorizada.",
                "",
                "```json",
                json.dumps(analysis, ensure_ascii=True, indent=2, allow_nan=False).replace(
                    "`", "\\u0060"
                ),
                "```",
            ]
        )
    return {
        "model_id": analysis["model_id"],
        "backend": analysis["backend"],
        "format": format,
        "content": content,
        "scope": "Historical test evidence; private to the requesting tenant",
    }
