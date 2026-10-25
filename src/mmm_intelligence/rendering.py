"""Self-contained local artifacts; no CDNs, external requests or deployment."""

import html
import json

from .scientific import decision_support


def report(model: dict) -> str:
    rows = [
        "# Relatório MMM exploratório",
        "",
        model["disclaimer"],
        "",
        f"Modelo: `{model['model_id']}`. Dataset: `{model['dataset_id']}`.",
        f"Motor: `{model['engine']}`. Dados sintéticos: **{model['synthetic']}**.",
        "",
        "## Desempenho temporal",
        "",
        "| Conjunto | MAE | RMSE | WAPE (%) | MAPE sem zeros (%) | R² |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for group, values in model["metrics"].items():
        rows.append(
            "| "
            + group
            + " | "
            + " | ".join(
                "indefinido" if values.get(k) is None else f"{values[k]:.6f}"
                for k in ("mae", "rmse", "wape_percent", "mape_nonzero_percent", "r2")
            )
            + " |"
        )
    rows += [
        "",
        "## Método e proveniência",
        "",
        f"Split: `{json.dumps(model['split'], ensure_ascii=False)}`.",
        f"Hash do dataset: `{model['dataset_sha256']}`.",
        "Ajuste preditivo não demonstra atribuição causal nem eficácia de canais.",
        "",
        "## Coeficientes",
        "",
        "| Feature | Coeficiente |",
        "|---|---:|",
    ]
    rows += [f"| {name} | {value:.8f} |" for name, value in model["coefficients"].items()]
    rows += [
        "",
        "## Incerteza",
        "",
        json.dumps(model.get("uncertainty", {"method": "não estimada"}), ensure_ascii=False),
        "",
        "## Diagnósticos e ressalvas",
        "",
    ]
    rows += [f"- {w}" for w in model["warnings"]]
    rows += [
        "",
        "## Validade da decisão",
        "",
        "Sucesso numérico não autoriza realocação. Receita modelada não é receita causal incremental; ROI/mROI causal não foram demonstrados.",
        json.dumps(decision_support(model), ensure_ascii=False),
        "",
        "Diagnósticos descritivos (sem certificação de independência ou identificação causal):",
        json.dumps(model["diagnostics"], ensure_ascii=False),
        "",
        "Execute audit_model para decomposição reconciliada, backtesting temporal, sensibilidade e insight rastreável.",
    ]
    rows += [
        "",
        "## Decisão",
        "",
        "Usar como investigação condicional. Nenhuma campanha ou verba real foi alterada.",
        "Calibração e validação empresarial exigem evidência experimental, origem autorizada e revisão humana.",
        "",
    ]
    return "\n".join(rows)


def dashboard(model: dict) -> str:
    payload = (
        json.dumps(model, ensure_ascii=True, allow_nan=False)
        .replace("<", "\\u003c")
        .replace("&", "\\u0026")
    )
    title = html.escape(model["model_id"])
    template = """<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'">
<title>MMM · __TITLE__</title><style>
body{font:16px system-ui;margin:0;background:#f3f0e8;color:#132e31}main{max-width:1100px;margin:auto;padding:32px}h1{font-size:36px;overflow-wrap:anywhere}section{background:white;padding:24px;margin:20px 0;border-radius:10px}svg{width:100%;height:250px}input{width:100%;box-sizing:border-box}label{display:block;margin:14px 0}small{color:#516468}.metrics{display:flex;gap:30px;flex-wrap:wrap}output{font-size:26px}pre{white-space:pre-wrap;overflow-wrap:anywhere}.warning{border-left:5px solid #bb642d;padding:16px}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:8px;border-bottom:1px solid #ddd}
</style><main><small>MMM INTELLIGENCE · LOCAL · EXPLORATÓRIO</small><h1>__TITLE__</h1>
<p class="warning" id="disclaimer"></p><section><h2>Teste temporal</h2><div class="metrics" id="metrics"></div><svg id="chart" viewBox="0 0 1000 250" role="img" aria-label="Observado e previsto no teste temporal"></svg><small>Escuro: observado. Laranja: previsto. Eixo horizontal: sequência de períodos; vertical: unidade do KPI.</small></section>
<section><h2>Explore um cenário</h2><p>Os pesos abaixo são normalizados. Gasto constante por período, controles mantidos no último observado e carryover histórico. Sem execução em contas.</p><label>Orçamento total <input id="budget" type="number" min="0" max="1000000000" step="100"></label><label>Horizonte (períodos) <input id="horizon" type="number" min="1" max="104" value="13"></label><div id="channels"></div><p>Previsão condicional do total: <output id="forecast"></output></p><small id="scenario-info"></small></section>
<section><h2>Coeficientes e limites</h2><table id="coefs"></table><pre id="warnings"></pre></section></main>
<script>"use strict";const model=__DATA__;const $=id=>document.getElementById(id);const fmt=x=>x===null?'indefinido':new Intl.NumberFormat('pt-BR',{maximumFractionDigits:3}).format(x);
$('disclaimer').textContent=model.disclaimer;$('warnings').textContent=model.warnings.join('\\n');for(const [k,v] of Object.entries(model.metrics.test)){const p=document.createElement('p');p.textContent=k+': '+fmt(v);$('metrics').append(p)}
const points=model.predictions.filter(x=>x.split==='test');const vals=points.flatMap(x=>[x.observed,x.predicted]);const lo=Math.min(...vals),hi=Math.max(...vals);for(const [field,color] of [['observed','#132e31'],['predicted','#bb642d']]){const line=document.createElementNS('http://www.w3.org/2000/svg','polyline');line.setAttribute('points',points.map((p,i)=>`${20+i*960/Math.max(points.length-1,1)},${230-(p[field]-lo)*210/Math.max(hi-lo,1)}`).join(' '));line.setAttribute('fill','none');line.setAttribute('stroke',color);line.setAttribute('stroke-width','2');$('chart').append(line)}
const channels=model.request.media_columns;$('budget').value=Object.values(model.state.reference_spend_per_period).reduce((a,b)=>a+b,0)*13;channels.forEach(c=>{const label=document.createElement('label');label.textContent=c;const input=document.createElement('input');input.type='range';input.min='0';input.max='100';input.value='33';input.dataset.channel=c;label.append(input);$('channels').append(label)});
for(const [k,v] of Object.entries(model.coefficients)){const row=document.createElement('tr');for(const text of [k,fmt(v)]){const cell=document.createElement('td');cell.textContent=text;row.append(cell)}$('coefs').append(row)}
function recalc(){const budget=Number($('budget').value),n=Number($('horizon').value),weights=[...$('channels').querySelectorAll('input')].map(x=>Number(x.value)),sum=weights.reduce((a,b)=>a+b,0);if(!Number.isFinite(budget)||budget<0||budget>1e9||!Number.isInteger(n)||n<1||n>104||sum===0){$('forecast').textContent='Entrada inválida';return}let stocks={...model.state.terminal_adstock},total=0;for(let i=0;i<n;i++){let y=model.coefficients.intercept;channels.forEach((c,j)=>{const p=model.media_parameters[c];stocks[c]=(1-p.decay)*budget*weights[j]/sum/n+p.decay*stocks[c];y+=model.coefficients[c]*stocks[c]/(p.half_saturation+stocks[c])});const days=(model.state.history_periods+i)*model.state.step_days;y+=model.coefficients.trend_years*days/365.25+model.coefficients.sin_year*Math.sin(2*Math.PI*days/365.25)+model.coefficients.cos_year*Math.cos(2*Math.PI*days/365.25);for(const c of model.request.control_columns)y+=model.coefficients[c]*model.state.last_controls[c];total+=y}$('forecast').textContent=fmt(total);$('scenario-info').textContent='Estimativa pontual; sem propagação da incerteza nesta visualização. Pode extrapolar o suporte dos dados.'}document.querySelectorAll('input').forEach(x=>x.addEventListener('input',recalc));recalc();</script></html>"""
    reasons = {
        "SYNTHETIC_DATA": "Os dados são fabricados e não constituem evidência de negócio.",
        "RANK_DEFICIENT": "As variáveis não permitem separar todos os efeitos do modelo.",
        "SCIENTIFIC_DIAGNOSTICS_UNAVAILABLE": "Este modelo antigo não tem os novos diagnósticos de identificação.",
        "CONDITIONAL_UNCERTAINTY_UNAVAILABLE": "Não há amostras suficientes para apresentar incerteza condicional.",
        "NO_HOLDOUT_IMPROVEMENT_OVER_MEAN_BASELINE": "O teste temporal não supera a referência simples de média histórica.",
        "SHORT_HISTORY": "A série tem cobertura sazonal limitada.",
        "EXTRAPOLATION": "O gasto está fora do intervalo observado no treino.",
        "NEGATIVE_PREDICTIONS": "O modelo produz valores negativos e precisa ser revisto.",
        "BOOTSTRAP_SHRINKAGE": "A penalização deslocou estimativas de incerteza; não há cobertura certificada.",
        "METADATA_MISSING": "Faltam definições e metadados necessários à interpretação dos dados.",
    }
    support = decision_support(model)
    explanation = "".join(
        "<li>" + html.escape(reasons.get(r, r)) + "</li>" for r in support["reasons"]
    )
    notice = (
        "<section><h2>Qualidade e limites da decisão</h2><p><strong>Não há autorização analítica para alterar a verba.</strong> O resultado abaixo é uma simulação condicional. ROI e mROI causais não foram demonstrados.</p><ul>"
        + explanation
        + "</ul><p>Revisar definições, estabilidade e experimentos antes de realocar. Intervalos bootstrap são condicionais e não têm cobertura certificada; este painel exibe estimativas pontuais.</p></section>"
    )
    template = template.replace(
        "<section><h2>Explore um cenário", notice + "<section><h2>Explore um cenário"
    )
    return template.replace("__TITLE__", title).replace("__DATA__", payload)
