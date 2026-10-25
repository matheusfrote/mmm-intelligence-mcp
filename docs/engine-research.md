# Pesquisa dos motores externos

Consulta em **24/10/2026** a documentação oficial, metadados dos distribuidores e código dos mantenedores. Este arquivo registra contratos pesquisados; **não comprova instalação, treino nem homologação local**. Exemplos abaixo são referências para os adaptadores e precisam de teste na versão efetivamente instalada.

## Versões e isolamento

| Motor | Referência instalável consultada | Python / sistema | Decisão proposta |
|---|---|---|---|
| Google Meridian | `google-meridian[schema]==2.1.0`, publicada em 25/09/2026 | README recomenda Python 3.11–3.13; metadata aceita >=3.10. CPU é uma opção documentada; CUDA é dirigida a Linux. Windows nativo precisa de smoke local. | Venv exclusiva; não adicionar à venv principal. |
| PyMC-Marketing | `pymc-marketing==1.3.0`, publicada em 22/10/2026 | Python >=3.12; pacote declara sistema independente. A instalação completa depende do stack numérico e do sampler. | Venv exclusiva Python 3.12; exportação NetCDF. |
| Meta Robyn em R | CRAN `Robyn` **3.12.1**, publicada em 02/07/2025 | R >=4.0; CRAN disponibiliza binários Windows. Nevergrad exige Python via reticulate. | Processo `Rscript` independente e contrato JSON. |
| Meta Robyn em Python | `robynpy==0.3.6` | Metadata Python >=3.8; ainda Beta e exige R + glmnet. | Opcional; não substituir a referência R silenciosamente. |

Fontes: [Meridian/PyPI](https://pypi.org/project/google-meridian/2.1.0/), [Meridian/metadata](https://pypi.org/pypi/google-meridian/2.1.0/json), [PyMC-Marketing/PyPI](https://pypi.org/project/pymc-marketing/1.3.0/), [instalação PyMC-Marketing](https://www.pymc-marketing.io/en/stable/getting_started/installation/index.html), [Robyn/CRAN](https://cran.r-project.org/package=Robyn), [robynpy/metadata](https://pypi.org/pypi/robynpy/0.3.6/json).

**Conflito confirmado:** Meridian 2.1.0 exige `arviz<0.20`, `numpy>=2.0.2,<2.4`, `pandas<3` e TensorFlow 2.21; PyMC-Marketing atual exige ArviZ >=1.2 e PyMC 6.x. Essas faixas ArviZ não têm interseção. Instalar os dois no mesmo ambiente não é uma configuração válida. O servidor base também tinha NumPy 2.5.4 na primeira entrega; não se deve rebaixá-lo implicitamente. A release estável Meridian depende explicitamente de `tfp-nightly==0.26.0.dev20260130`; não chamar todo seu grafo de dependências de estável. Fontes: [pyproject Meridian v2.1.0](https://raw.githubusercontent.com/google/meridian/v2.1.0/pyproject.toml), [pyproject PyMC-Marketing](https://raw.githubusercontent.com/pymc-labs/pymc-marketing/main/pyproject.toml).

O pacote PyPI **`robyn` é um framework web diferente**. A página do Meta aponta `robynpy`; a instalação nunca deve usar o homônimo por aproximação. Fonte: [guia oficial Meta](https://facebookexperimental.github.io/Robyn/docs/robyn-api/).

## Google Meridian

### Dados e ajuste

Imports concretos: `from meridian.data import load`; `from meridian.model import model, spec`.

`load.CoordToColumns(time=..., kpi=..., controls=[...], media=[...], media_spend=[...])` define o mapeamento. `load.DataFrameDataLoader(df=..., coord_to_columns=..., kpi_type="revenue", media_to_channel={...}, media_spend_to_channel={...}).load()` retorna `InputData`. As datas usam ISO; a modelagem nacional pode omitir geo e população. Mídia/exposição e gasto são conceitos separados: usar gasto como proxy de exposição deve ser uma decisão explícita do adaptador. Fonte: [loader v2.1.0](https://raw.githubusercontent.com/google/meridian/v2.1.0/meridian/data/load.py).

`model.Meridian(input_data=data, model_spec=model_spec)` constrói o modelo. `sample_prior(n_draws=..., seed=...)` e `sample_posterior(n_chains=..., n_adapt=..., n_burnin=..., n_keep=..., seed=...)` geram as amostras. O resultado fica em `mmm.inference_data`; `sample_posterior` modifica esse estado e não deve ser tratado como retorno contendo o modelo. `mmm.review()` executa verificações de saúde. Fonte: [modelo v2.1.0](https://raw.githubusercontent.com/google/meridian/v2.1.0/meridian/model/model.py).

O split temporal pode ser expresso por `spec.HoldoutSpec(spec=[spec.DateRange(inicio_teste, None)])`, entregue a `spec.ModelSpec(holdout=...)`. Os KPIs do holdout saem do treinamento; mídia permanece para carryover. `holdout_id` existe, porém é obsoleto. A especificação também aceita `max_lag` e `adstock_decay_spec="geometric"`. Fonte: [ModelSpec v2.1.0](https://raw.githubusercontent.com/google/meridian/v2.1.0/meridian/model/spec.py).

### Previsão e limites

`from meridian.analysis import analyzer`; `analyzer.Analyzer(mmm).expected_outcome(aggregate_geos=False, aggregate_times=False, use_kpi=True)` fornece draws do resultado esperado por período. `predictive_accuracy(use_kpi=True)` fornece R², MAPE e wMAPE por conjunto. Para padronizar MAE/WAPE/R² do servidor, calcular as métricas sobre a média posterior e a máscara temporal persistida, documentando unidades.

`expected_outcome(new_data=DataTensors(...))` permite cenários com as mesmas dimensões históricas. **A API explicitamente não aceita outro número de períodos para previsão futura**. Logo, não chamar um contrafactual histórico de forecast futuro nem reaproveitar o horizonte do motor Ridge sem definir e validar a extensão de tendência/baseline. Fonte: [Analyzer v2.1.0](https://raw.githubusercontent.com/google/meridian/v2.1.0/meridian/analysis/analyzer.py).

### Persistência sem pickle

Preferir o extra `schema` e o serializer oficial:

```python
from meridian.schema.serde import meridian_serde

meridian_serde.save_meridian(mmm, caminho_interno_binpb)
restored = meridian_serde.load_meridian(caminho_interno_binpb)
```

A extensão precisa ser `.binpb`, `.txtpb` ou `.textproto`. Não usar `save_mmm/load_mmm`, que persistem pickle/joblib e estão obsoletos. A página de documentação apresenta um import abreviado; o caminho acima é o módulo presente na tag 2.1.0. Manter registries padrão, não permitir função recebida do cliente e não usar `force_deserialization=True`. Publicar o arquivo por escrita exclusiva dentro da raiz autorizada, pois o serializer abre seu destino em modo de escrita. Fontes: [guia de persistência](https://developers.google.com/meridian/docs/user-guide/saving-model-object), [serializer v2.1.0](https://raw.githubusercontent.com/google/meridian/v2.1.0/meridian/schema/serde/meridian_serde.py).

Smoke proposto: 104–156 semanas sintéticas, um geo, 2–3 canais; poucas amostras/chains e tamanho de árvore limitado, com timeout. Verificar fit, valores finitos, máscara holdout, persistência, reinício e igualdade das previsões condicionais restauradas. Poucos draws servem ao teste de execução e **não demonstram convergência**. Essa configuração de teste é uma proposta do projeto, não uma recomendação estatística do Google.

## PyMC-Marketing

### Contrato mínimo

```python
from pymc_marketing.mmm.mmm import MMM
from pymc_marketing.mmm.components.adstock import GeometricAdstock
from pymc_marketing.mmm.components.saturation import LogisticSaturation

mmm = MMM(
    date_column="date",
    channel_columns=channel_names,
    control_columns=control_names,
    adstock=GeometricAdstock(l_max=8),
    saturation=LogisticSaturation(),
)
idata = mmm.fit(
    X=X_train, y=y_train,
    chains=2, cores=1, draws=50, tune=50,
    random_seed=42, progressbar=False,
)
```

O import de `MMM` deve identificar o módulo concreto; evitar depender do alias genérico ao persistir modelos. O construtor e transformações aparecem na [API MMM](https://www.pymc-marketing.io/en/stable/api/generated/pymc_marketing.mmm.mmm.MMM.html). O método `fit` atual suporta `mcmc`, `map`, `demz`, `advi` e `fullrank_advi`, recebe kwargs do sampler e retorna `xr.DataTree`: [API fit](https://www.pymc-marketing.io/en/stable/api/generated/classmethods/pymc_marketing.mmm.mmm.MMM.fit.html). Não assumir `arviz.InferenceData` da geração anterior em um adaptador 1.x.

Previsões: `mmm.sample_posterior_predictive(X=X_test, extend_idata=False, combined=False, include_last_observations=True, random_seed=42)` retorna `xr.Dataset`. A opção de últimas observações preserva continuidade do adstock na fronteira; validar as dimensões e a escala do target antes de calcular métricas. Para futuros períodos, fornecer as datas e canais/controles no mesmo esquema do treino. Fonte: [API posterior predictive](https://www.pymc-marketing.io/en/stable/api/generated/classmethods/pymc_marketing.mmm.mmm.MMM.sample_posterior_predictive.html).

Persistência: `mmm.save(caminho_interno_nc, engine="h5netcdf")`; `restored = MMM.load(caminho_interno_nc)`; não desativar a checagem do ID. A implementação atual inclui h5netcdf e h5py nas dependências. Fontes: [API save](https://www.pymc-marketing.io/en/stable/api/generated/classmethods/pymc_marketing.mmm.mmm.MMM.save.html), [API load](https://www.pymc-marketing.io/en/stable/api/generated/classmethods/pymc_marketing.mmm.mmm.MMM.load.html), [manifesto de dependências](https://raw.githubusercontent.com/pymc-labs/pymc-marketing/main/pyproject.toml).

No Windows, começar pelo sampler CPU e processo único. O PyMC atual permite pip; conda-forge é alternativa documentada para controlar BLAS ou usar backend C legado. Não declarar que GCC/Conda são sempre obrigatórios: isso depende da versão/backend. Fonte: [instalação PyMC](https://www.pymc.io/projects/docs/en/latest/installation.html).

Smoke proposto: mesmo dataset sintético e split do motor local, 2 chains curtas, sem plots nem MLflow; comparar previsão antes/depois de NetCDF e reinício; verificar amostras e diagnósticos disponíveis. A aprovação funcional do smoke não basta para validar R-hat, ESS, divergências ou calibrar incerteza.

## Meta Robyn

### Opção recomendada para um adaptador confiável

Usar R **3.12.1 do pacote Robyn** (não confundir a versão do pacote com a versão do interpretador R), via executável `Rscript` configurado pelo operador e argumentos fixos, sem shell. O metadata CRAN identifica R >=4.0 e binários Windows. A instalação do Robyn R requer também Nevergrad por reticulate. Fontes: [CRAN](https://cran.r-project.org/package=Robyn), [instalação oficial](https://facebookexperimental.github.io/Robyn/docs/installation/).

Contrato R: `robyn_inputs()` recebe dataset, colunas, sinais e hiperparâmetros; `robyn_run(InputCollect, trials=1, iterations=200, cores=1, ts_validation=TRUE, seed=42)` é uma base de smoke documentada, não ajuste adequado de produção. `paid_media_signs` controla sinais. Usar `robyn_outputs(..., export=FALSE, plot_pareto=FALSE)` para preparar candidatos. `robyn_write(InputCollect, OutputCollect, select_model=..., add_data=TRUE, export=FALSE)` produz objeto exportável como JSON; `robyn_read` e `robyn_recreate` recompõem o fluxo. `robyn_response` fornece resposta de mídia, não um método universal de forecast com todos os controles. Fonte: [manual CRAN](https://cran.r-project.org/web/packages/Robyn/refman/Robyn.html).

Persistir seleção explícita, coeficientes, hiperparâmetros, dados sintéticos de origem e JSON oficial; não introduzir RDS como carga arbitrária. O código de referência dos serializers está em [json.R](https://raw.githubusercontent.com/facebookexperimental/Robyn/main/R/R/json.R). O exemplo oficial utiliza o dataset `dt_simulated_weekly`: [demo.R](https://raw.githubusercontent.com/facebookexperimental/Robyn/main/demo/demo.R).

### Alternativa Python e seus riscos concretos

`robynpy==0.3.6` é uma tradução Beta da versão R 3.11.1, reconhecida pelos mantenedores como sujeita a bugs. Os requisitos publicados incluem `rpy2==3.5.16`, `nlopt==2.9.1` e `kaleido==0.2.1`, além de Prophet/Nevergrad. Portanto não é uma implementação Python sem R nem paridade garantida com Robyn R 3.12.1. Fonte: [metadata robynpy](https://pypi.org/pypi/robynpy/0.3.6/json).

O fluxo concreto do código é `from robyn.robyn import Robyn`; construção com `working_dir`; `initialize(mmm_data, holidays_data, hyperparameters)`; `feature_engineering(display_plots=False, export_plots=False)`; `train_models(trials_config=..., ts_validation=True, cores=1, display_plots=False, export_plots=False)`. O resultado é `ModelOutputs`; não assumir API sklearn `fit/predict/save`. Fonte: [interface Robyn Python](https://raw.githubusercontent.com/facebookexperimental/Robyn/main/python/src/robyn/robyn.py).

O upstream rpy2 vem corrigindo Windows, mas as melhorias da série 3.6 não provam funcionamento do pin 3.5.16 do robynpy. Por isso o wrapper Python pode falhar antes do fit. Fonte: [notas oficiais rpy2](https://github.com/rpy2/rpy2/blob/master/NEWS). Não trocar o pin sem registrar a divergência e repetir o ciclo real.

## Critérios de aceitação dos adaptadores

Estas são decisões propostas do projeto, não afirmações de recursos já prontos:

1. Processo isolado por motor com versões registradas, ambiente independente, timeout e resultado JSON; execução local sem serviços externos.
2. Descoberta deve distinguir `unavailable`, `installed_unverified`, `smoke_verified` e erro de runtime. Import bem-sucedido não equivale a integração homologada.
3. Treinar somente dados sintéticos por padrão; preservar procedência, canais, escalas, controles, datas e máscara temporal.
4. Persistir por formato nativo seguro em diretório privado e publicar sem sobrescrever. Hash e tamanho máximo antes da leitura; não receber caminhos arbitrários nem código/registries do cliente.
5. Testar treino, consulta, previsão/cenário suportado, serialização e novo processo. Comparar valores antes/depois, respeitando tolerância numérica e seeds.
6. Separar erro de execução, diagnóstico de convergência e identificação causal. Reportar limites e diagnósticos ausentes; manter `exploratory=true`.
7. Meridian: marcar previsão futura como não suportada enquanto só houver `expected_outcome` histórico. Robyn: não prometer forecast completo a partir de `robyn_response`. Não produzir números usando Ridge e rotulá-los com o nome de outro motor.

Não houve nesta pesquisa instalação de pacotes, alteração de campanhas, uso de dados reais, publicação, criação de contas ou execução de treinos. As fontes confirmam caminhos técnicos; a evidência de execução deve ser produzida pelos testes do projeto.
