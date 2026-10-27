"""Local analytical panels; only textContent receives model data."""


def enhance_dashboard(template: str) -> str:
    navigation = """<nav aria-label="Etapas da análise"><a href="#overview">Visão geral</a><a href="#quality">Dados</a><a href="#residuals">Resíduos</a><a href="#decomposition">Componentes</a><a href="#response-curves">Resposta</a><a href="#simulation">Simulação</a><a href="#exports">Exportar</a></nav>
<section id="overview"><h2>Visão geral</h2><p id="overview-text"></p><details><summary>Configuração, versões e diagnósticos</summary><pre id="configuration"></pre></details><p>Nenhum treinamento é executado pelo HTML. Treine e compare motores pelas ferramentas MCP; este painel representa um ajuste Ridge persistido.</p></section>
<section id="quality"><h2>Qualidade dos dados</h2><p id="quality-summary"></p><div class="table-scroll"><table id="quality-table"></table></div><details><summary>Alertas e evidências completas</summary><pre id="quality-details"></pre></details></section>"""
    panels = """<section id="residuals"><h2>Resíduos no teste</h2><svg id="residual-chart" viewBox="0 0 1000 250" role="img" aria-label="Resíduo observado menos previsto"></svg><small id="residual-caption"></small></section>
<section id="decomposition"><h2>Componentes ajustados</h2><p>Componentes somam a previsão, incluindo intercepto, tendência, sazonalidade e controles. Não são efeitos causais incrementais.</p><div class="table-scroll"><table id="component-table"></table></div><p id="component-error"></p></section>
<section id="response-curves"><h2>Resposta condicional da mídia</h2><p>Curvas estacionárias b × x / (K + x), após estabilização do adstock. Eixo horizontal: gasto por período dentro da faixa de treino; vertical: componente modelado do KPI. Não são ROI, lucro nem a projeção dinâmica abaixo.</p><div id="curves"></div></section>"""
    exports = """<section id="exports"><h2>Exportação e próximos passos</h2><p id="abstention"></p><p>Investigue tracking, confundidores e estabilidade; predefina KPI, população, horizonte e incerteza para um teste de incrementalidade independente.</p><p><a id="download-json" download="mmm-model.json">Baixar JSON do modelo</a> · <a id="download-csv" download="mmm-test.csv">Baixar CSV do teste</a></p><p>HTML: salve este arquivo. Markdown e comparação multimotor: use generate_report, export_analysis e compare_models pelo MCP. Nenhum envio a serviços externos.</p></section>"""
    script = r"""
function tableRows(id,rows){const t=$(id);for(const [i,row] of rows.entries()){const tr=document.createElement('tr');for(const text of row){const cell=document.createElement(i===0?'th':'td');cell.textContent=String(text);tr.append(cell)}t.append(tr)}}
function drawLine(svg,values,color){const min=Math.min(0,...values),max=Math.max(0,...values),width=Math.max(max-min,1);const line=document.createElementNS('http://www.w3.org/2000/svg','polyline');line.setAttribute('points',values.map((v,i)=>`${20+i*960/Math.max(values.length-1,1)},${230-(v-min)*210/width}`).join(' '));line.setAttribute('fill','none');line.setAttribute('stroke',color);line.setAttribute('stroke-width','2');svg.append(line);for(const [y,value] of [[230,min],[20,max]]){const label=document.createElementNS('http://www.w3.org/2000/svg','text');label.setAttribute('x','22');label.setAttribute('y',String(y));label.setAttribute('font-size','12');label.textContent=fmt(value);svg.append(label)}}
const ctx=model.dashboard_context||{},quality=ctx.quality||{};
$('overview-text').textContent=`Dataset ${model.dataset_id} · KPI ${model.request.target_column} · ${model.predictions[0].date} a ${model.state.last_date} · dados ${model.synthetic?'sintéticos':'declarados reais'} · ${model.state.step_days===7?'semanal':'diário'}`;
$('configuration').textContent=JSON.stringify({versions:model.versions,request:model.request,diagnostics:model.diagnostics,uncertainty:model.uncertainty||{status:'unavailable'}},null,2);
$('quality-summary').textContent=quality.rows?`${quality.rows} períodos · ${quality.valid?'validação estrutural aprovada':'problemas impeditivos'} · ${(quality.alerts||[]).length} alertas descritivos`:'Qualidade detalhada indisponível neste artefato.';
$('quality-details').textContent=JSON.stringify(quality.alerts||[],null,2);
tableRows('quality-table',[['Variável','Ausentes/inválidos','Mínimo','Máximo','Fração zero'],...Object.entries(quality.columns||{}).map(([k,v])=>[k,v.missing_or_invalid,fmt(v.min??null),fmt(v.max??null),fmt(v.zero_fraction??null)])]);
drawLine($('residual-chart'),points.map(p=>p.observed-p.predicted),'#bb642d');$('residual-caption').textContent=`${points[0].date} a ${points.at(-1).date}; observado menos previsto, na unidade do KPI. Diagnóstico descritivo.`;
const decomposition=ctx.decomposition||{};tableRows('component-table',[['Feature','Total ajustado','Intervalo condicional 90%'],...Object.entries(decomposition.component_totals||{}).map(([k,v])=>[k,fmt(v),decomposition.conditional_component_intervals_90?decomposition.conditional_component_intervals_90[k].map(fmt).join(' a '):'indisponível'])]);$('component-error').textContent=`Erro máximo de reconciliação: ${fmt(decomposition.maximum_reconciliation_error??null)}. Intervalos condicionais não certificam cobertura.`;
channels.forEach(c=>{const p=model.media_parameters[c],box=document.createElement('div'),title=document.createElement('h3'),svg=document.createElementNS('http://www.w3.org/2000/svg','svg');title.textContent=c;svg.setAttribute('viewBox','0 0 1000 250');svg.setAttribute('role','img');svg.setAttribute('aria-label','Resposta estacionária '+c);const values=Array.from({length:51},(_,i)=>{const x=p.training_spend_min+i*(p.training_spend_max-p.training_spend_min)/50;return model.coefficients[c]*x/(p.half_saturation+x)});drawLine(svg,values,'#24766b');const caption=document.createElement('small');caption.textContent=`Faixa de treino: ${fmt(p.training_spend_min)} a ${fmt(p.training_spend_max)}; retenção ${fmt(p.decay)}; K ${fmt(p.half_saturation)}.`;box.append(title,svg,caption);$('curves').append(box)});
$('abstention').textContent=model.decision_support.message;
const csv=['date,observed,predicted,residual',...points.map(p=>[p.date,p.observed,p.predicted,p.observed-p.predicted].join(','))].join('\n');
for(const [id,data,type] of [['download-json',JSON.stringify(model,null,2),'application/json'],['download-csv',csv,'text/csv']]){$(id).href=URL.createObjectURL(new Blob([data],{type}))}
"""
    template = template.replace("<h1>__TITLE__</h1>", "<h1>Análise de marketing</h1>")
    template = template.replace(
        "</style>",
        "nav{display:flex;gap:12px;flex-wrap:wrap}nav a,#exports a{color:#145f57;padding:8px;background:#e3eeea;border-radius:6px}section{scroll-margin-top:16px}.table-scroll{overflow:auto}td,th{overflow-wrap:anywhere}svg{display:block}h3{overflow-wrap:anywhere}@media(max-width:600px){main{padding:14px}section{padding:16px}h1{font-size:28px}}\n</style>",
    )
    template = template.replace(
        '<p class="warning" id="disclaimer">', navigation + '<p class="warning" id="disclaimer">'
    )
    template = template.replace(
        "<section><h2>Explore um cenário",
        panels + '<section id="simulation"><h2>Explore um cenário',
    )
    template = template.replace("</main>", exports + "</main>")
    return template.replace("</script>", script + "</script>")
