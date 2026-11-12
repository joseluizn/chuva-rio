# Como atualizar os dados

Este documento descreve como os dados diários de chuva do Rio de Janeiro são atualizados, automática e manualmente, e como conferir o resultado. Tudo foi escrito para ser seguido por quem nunca viu o repositório.

## 1. Visão geral do fluxo

```
Open-Meteo Historical Weather API (sem chave)
   │   scripts/fetch_data.py   (baixa, valida, grava atomicamente)
   ▼
data/daily/era5.csv  ecmwf_ifs.csv  best_match.csv  era5_cloud.csv  meta.json
   │   scripts/model_periods.py → data/derived/periodos_abr_out.json   (modelo por decêndio; ver docs/modelo_periodos.md)
   │   scripts/build_main.py   → site/index.html      (usa scripts/main_template.html)
   │   scripts/build_full.py   → site/completo.html   (usa scripts/full_template.html; ambos usam scripts/common.py)
   ▼
site/  ──(push na main)──►  GitHub Actions "Deploy Pages"  ──►  https://joseluizn.github.io/chuva-rio/
```

- **Fonte**: `https://archive-api.open-meteo.com/v1/archive`, variável `daily=precipitation_sum`, ponto (-22.9068, -43.1729), fuso `America/Sao_Paulo`, de 1995-01-01 até ontem. Modelos: `era5` (série principal), `ecmwf_ifs` e `best_match` (comparação). Ver `docs/analise_modelos.md` para o motivo de a série principal ser o ERA5 (o `best_match` passa a ser ECMWF IFS em 2017 e cria uma descontinuidade).
- **CSV**: colunas `date,precip_mm`; célula vazia = dado ausente. O arquivo é sempre o período completo.
- **Nebulosidade** (`era5_cloud.csv`): mesma API e mesma célula do ERA5 de chuva (`models=era5`). Diário: `cloud_cover_mean`, `sunshine_duration`, `daylight_duration`; horário: `cloud_cover`, de que se calcula a média das 9 horas locais de 09 a 17 h (`cloud_daytime_0917_pct`). Colunas: `date,cloud_cover_mean_pct,sunshine_min,daylight_min,cloud_daytime_0917_pct`; célula vazia = dado ausente (os últimos dias, pelo mesmo atraso do ERA5). **Dia de céu aberto** = nebulosidade diurna ≤ 30% (`OPEN_THR` em `scripts/common.py`), a classe "clear" (0 a 3/10) do NOAA/NCEI ([Comparative Climatic Data](https://www.ncei.noaa.gov/products/land-based-station/comparative-climatic-data)). Só é baixada na execução padrão (sem `--model`); `--cloud` força e `--skip-cloud` pula. Nebulosidade de reanálise é modelo, não observação, e não há referência observada conferida; a fração de insolação foi checada e descartada (ver `docs/modelo_periodos.md`).
- **Referências estáticas** (`data/refs/`) não passam por esse fluxo; ver seção 5.

### Por que baixar tudo a cada vez (e não só o recente)

São 4 requisições por modelo (blocos de 10 anos), cerca de 12 no total, mais cerca de 4 diárias e 7 horárias (blocos de 5 anos) para a nebulosidade, muito abaixo do limite gratuito. Baixar o período completo permite comparar toda a série com o CSV atual e detectar revisões silenciosas da reanálise. Uma atualização incremental (só os últimos 30 dias) seria mais leve, mas não enxergaria revisões antigas.

### Validações antes de gravar (tudo ou nada)

O `fetch_data.py` só grava se **todos** os modelos passarem:

1. Resposta bem formada (`daily.time` e `daily.precipitation_sum` do mesmo tamanho, unidade `mm`, valores numéricos ou nulos).
2. Datas contínuas, sem duplicatas, cobrindo exatamente do início ao fim pedidos.
3. Valores finitos e ≥ 0.
4. Nulos só no início (o `ecmwf_ifs` começa em 2017) ou no fim (atraso do ERA5, ~5-6 dias); nulo no meio da série é erro. Último valor com mais de 15 dias de atraso também é erro.
5. **Nenhum dia anterior a hoje − 60 dias mudou mais que 0,2 mm** em relação ao CSV atual (nem virou nulo). Dias mais recentes podem ser revisados livremente.

A nebulosidade passa por validações análogas, no mesmo "tudo ou nada" (uma falha nela também impede gravar a chuva): células de grade iguais às do ERA5 de chuva; nebulosidade entre 0 e 100%; `sunshine` entre 0 e `daylight`; `daylight` presente e plausível; nulos coerentes entre `cloud_cover_mean` e `sunshine`; as 9 horas de 09 a 17 h de cada dia presentes (dia com hora faltando vira nulo e, no meio da série, é erro); e, para dias antigos, nenhuma revisão acima de 2 pontos percentuais (`--allow-revisions` libera, como na chuva).

Se algo falha, o script sai com código 1, imprime o motivo (e os 10 maiores desvios, no caso de revisões) e não altera nenhum arquivo.

## 2. Atualização automática (GitHub Actions)

Workflow `.github/workflows/update-data.yml` ("Update data"):

- **Quando**: dia 7 de cada mês, 09:17 UTC (≈ 06:17 em Brasília), depois do atraso do ERA5. Também pode ser disparado à mão.
- **O que faz**: checkout → Python 3.12 → testes do coletor → `python scripts/fetch_data.py` → `python scripts/model_periods.py` (pula com aviso se não existir; grava `data/derived/periodos_abr_out.json`) → `python scripts/build_main.py` → `python scripts/build_full.py` (pula com aviso se o script não existir) → se houver diferença em `data/` ou `site/`, faz commit `dados: atualização automática AAAA-MM-DD` e push na `main`.
- **Publicação**: o commit altera `site/`. Como pushes feitos com o `GITHUB_TOKEN` não disparam outros workflows, o workflow `pages.yml` também escuta o término bem-sucedido de "Update data" (`workflow_run`) e publica o site.
- **Permissões**: o repositório precisa permitir que Actions escrevam: Settings → Actions → General → Workflow permissions → "Read and write permissions" (o workflow já declara `contents: write`). Se a `main` tiver proteção de branch que bloqueie pushes do bot, é preciso liberar o `github-actions[bot]`.

### Disparar manualmente

- Pela interface: aba **Actions → Update data → Run workflow** (branch `main`).
- Pela CLI: `gh workflow run update-data.yml` e depois `gh run watch` (ou `gh run list --workflow update-data.yml`).

### Quando a Action falha

O job falha e o GitHub envia e-mail ao dono do repositório. Nada é commitado.

1. Abra o log do passo "Baixar e validar dados (Open-Meteo)" (Actions → execução com ✗ → passo).
2. Leia a linha `ERRO`:
   - **`HTTP 4xx/5xx` ou `falha após N tentativas`**: problema de rede/API. Rode o workflow de novo mais tarde. HTTP 429 indica limite de uso (ver seção 8).
   - **`valores anteriores a … mudaram mais que 0.2 mm`**: a fonte revisou dias históricos. Pode ser legítimo (por exemplo, o ERA5T provisório sendo trocado pelo ERA5 final, 2 a 3 meses depois; ou uma nova versão da reanálise) ou um problema. Não force às cegas: rode localmente, inspecione e só então use `--allow-revisions`:
     ```bash
     cp -r data/daily /tmp/daily_antes
     python3 scripts/fetch_data.py --allow-revisions
     git diff --stat data/daily          # quantos dias mudaram
     git diff data/daily/era5.csv | head -60
     ```
     Se as mudanças forem pequenas e esparsas, siga com os builds e o commit (seção 3, passos 4 a 6). Se forem grandes ou sistemáticas (por exemplo, o ponto de grade mudou: veja `returned_latitude` em `meta.json`), descarte com `git checkout data/daily` e investigue antes de publicar. Os números citados no site e em `docs/analise_modelos.md` podem precisar de revisão.
   - **`nulos no meio da série`, `datas não contínuas`, `valor inválido`, `resposta sem daily…`**: a API devolveu algo inesperado. Rode de novo; se persistir, abra a URL da requisição no navegador e compare com a documentação da API.
   - **`último valor … dias antes`**: a fonte está atrasada além de 15 dias. Aguarde e tente de novo.
3. Falha em "Reconstruir páginas": o erro está nos scripts de build, não nos dados; reproduza localmente (seção 3).

## 3. Atualização manual local

Requisitos: Python 3.9+ e Git. Nenhuma dependência além da biblioteca padrão do `fetch_data.py`; os scripts de build podem ter requisitos próprios (ver o topo de cada um).

```bash
# 1. clonar (ou `git pull` se já tem)
git clone https://github.com/joseluizn/chuva-rio.git
cd chuva-rio

# 2. (opcional) conferir que o coletor passa nos testes, sem rede
python3 -m unittest scripts/test_fetch_data.py -v

# 3. baixar e validar (use --dry-run para só validar, sem gravar)
python3 scripts/fetch_data.py --dry-run
python3 scripts/fetch_data.py

# 4. recalcular o modelo por decêndio e reconstruir as páginas
python3 scripts/model_periods.py   # data/derived/periodos_abr_out.json
python3 scripts/build_main.py      # site/index.html
python3 scripts/build_full.py      # site/completo.html

# 5. abrir e conferir (seção 6)
xdg-open site/index.html           # macOS: open site/index.html

# 6. publicar
git add data site
git commit -m "dados: atualização manual $(date +%F)"
git push
```

O push na `main` com mudanças em `site/` dispara o workflow "Deploy Pages". Opções úteis do coletor: `--model era5` (repetível), `--dry-run`, `--allow-revisions`, `--tolerance MM`, `--recent-days N`. Veja `python3 scripts/fetch_data.py --help`.

## 4. Como mudar parâmetros

Os padrões ficam nas constantes do topo de `scripts/fetch_data.py`; todos têm opção de linha de comando equivalente.

| O que | Como |
|---|---|
| Ponto geográfico | `--lat`/`--lon` ou `LATITUDE`/`LONGITUDE`. Muda **toda** a série, então exige `--allow-revisions` na primeira rodada, e as referências estáticas (Alerta Rio, INMET, Galeão) deixam de ser comparáveis. Rótulos e textos do site mencionam o ponto e precisam ser revistos. Confira `returned_latitude/longitude` em `meta.json`: o ERA5 usa grade de ~0,25°, então pontos próximos caem na mesma célula. |
| Período inicial | `--start-date` ou `START_DATE`. Encurtar o período apaga histórico (o script só avisa se algo existente for alterado, não se for removido); alongar exige que a API tenha dados (ERA5 vai a 1940). Os scripts de build podem assumir 1995; confira. |
| Limiar da checagem de revisão | `--tolerance` (padrão 0,2 mm) e `--recent-days` (padrão 60). Os valores têm resolução de 0,1 mm. |
| Atraso máximo aceito | `--max-lag` (padrão 15 dias). |
| Acrescentar um modelo | (1) acrescente o nome do modelo (valor de `models=` da API, ver https://open-meteo.com/en/docs/historical-weather-api) à lista `MODELS` em `fetch_data.py`; (2) rode o coletor: ele cria `data/daily/<modelo>.csv` e a entrada em `meta.json`; (3) use o modelo em `scripts/common.py`/builds; (4) acrescente-o em `docs/analise_modelos.md`. Cuidado: um modelo que retorna tudo nulo no ponto (caso do `era5_land` aqui) é rejeitado pela validação "série inteira nula". |
| Dia/hora da Action | linha `cron` em `.github/workflows/update-data.yml` (UTC; evite o minuto 0). |

## 5. Referências estáticas (`data/refs/`)

Não são atualizadas automaticamente: são comparações externas usadas para contextualizar o ERA5. Atualize à mão, no máximo uma vez por ano.

| Arquivo | Origem | Formato |
|---|---|---|
| `monthly_means_alertario.csv` | Relatório Anual de Chuva do Sistema Alerta Rio (prefeitura do Rio), tabela de média mensal da rede pluviométrica | Linhas iniciais `#` com a fonte; cabeçalho `month,mean_mm_<período>_rel<ano>`; 12 meses `JAN…DEZ` + `ANUAL_TOTAL` + `ANUAL_MEDIA`; decimal com ponto |
| `refs.json` | Resume Alerta Rio (`alertario`) e INMET (`inmet`) | Por fonte: `short`, `label`, `monthly_mm` (12 valores, jan a dez), `annual_mm`, `url`, `source_name`, `status`; INMET também `wet_days` (12), `annual_wet_days`, `period_note` |
| `galeao_ghcn.json`, `ghcn_BRM00083746_1995_2025.csv` | NOAA NCEI GHCN-Daily, estação BRM00083746 (Galeão) | CSV no formato bruto do NCEI (`STATION,NAME,LATITUDE,LONGITUDE,ELEVATION,DATE,PRCP`); o JSON guarda a URL, a cobertura e totais dos anos com cobertura > 95% |

### Alerta Rio

Relatórios anuais em PDF, hospedados em `https://www.sistema-alerta-rio.com.br/wp-content/uploads/2016/07/RELATORIO_ANUAL_CHUVA_<ANO>.pdf` (o `refs.json` aponta para o de 2025; o padrão do nome foi inferido dos arquivos usados, confirme no site em "Relatórios"). Passos: baixe o PDF do ano mais recente, localize a tabela "Média Mensal da Rede Pluviométrica (mm)" (período 1997 até o ano anterior ao relatório), copie os 12 valores mensais e o total anual para `monthly_means_alertario.csv` (nova coluna ou substituição da coluna mais antiga, mantendo o comentário `#` de fonte) e para `refs.json` (`monthly_mm`, `annual_mm`, `label`, `url`, `source_name`). Valores atuais foram lidos por resumo automático do PDF, não por leitura direta: o campo `status` diz "referência, não conferida". Confira à mão contra o PDF e, ao conferir, atualize o `status`.

### INMET

O `refs.json` usa a normal citada na Wikipédia (https://en.wikipedia.org/wiki/Rio_de_Janeiro), com período inconsistente na fonte (1981–2010 ou 1961–1990). A fonte primária são as Normais Climatológicas do INMET, publicadas como arquivos XLSX por período (portal do INMET, página "Normais Climatológicas": https://portal.inmet.gov.br/normais; o endereço pode mudar, procure por "normais climatológicas"). Para substituir: baixe o XLSX do período 1991–2020, localize a estação Rio de Janeiro (o `refs.json` registra "Saúde"; confira o nome exato no arquivo), copie precipitação acumulada mensal e número de dias com precipitação ≥ 1 mm para `monthly_mm`/`wet_days`, e ajuste `label`, `period_note`, `url` e `status`.

### Galeão (NOAA NCEI)

Baixe com a URL registrada em `galeao_ghcn.json`, ajustando `endDate`:

```bash
curl -o data/refs/ghcn_BRM00083746_1995_2025.csv \
  "https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries&stations=BRM00083746&startDate=1995-01-01&endDate=2025-12-31&dataTypes=PRCP&format=csv&units=metric"
```

Renomeie o arquivo se o ano final mudar, recalcule em `galeao_ghcn.json` os anos com cobertura > 95% (`days_obs`, `total_mm`, `wet_days_ge1`) e atualize `note`. A cobertura da estação é baixa (29% dos dias em 1995-2025), então serve só de checagem pontual.

Depois de qualquer mudança em `data/refs/`, rode os builds e confira os números citados no site.

## 6. Checklist pós-atualização

- [ ] `python3 scripts/fetch_data.py` terminou com código 0 e imprimiu "Gravado em …".
- [ ] `git diff --stat data/daily`: as três CSVs ganharam linhas novas só no fim (e valores dos últimos dias do ERA5 preenchidos); nenhuma mudança espalhada em anos antigos.
- [ ] `data/daily/meta.json`: `accessed` é hoje; `last_date_with_value` do `era5` está ~5-6 dias atrás; `end_date` é ontem; `returned_latitude/longitude` e `elevation_m` iguais aos de antes (-22.75, -43.25 para o ERA5).
- [ ] `data/daily/era5_cloud.csv` ganhou linhas só no fim; `meta.json` → `cloud`: `last_date_with_value` ~5-6 dias atrás, `same_grid_cell_as_rain_era5` verdadeiro. `data/derived/periodos_abr_out.json` mudou pouco (mesmas sementes).
- [ ] Abra `site/index.html` e `site/completo.html` no navegador: carregam sem erro no console.
- [ ] O ano parcial avançou (a data "até" mostrada no site é a nova) e o ano corrente continua marcado como parcial.
- [ ] Totais anuais de anos fechados não mudaram. Confira também o texto de abertura (o "lead") e os totais e razões citados; frases com números escritos à mão em `scripts/build_*.py` ou `docs/` podem ficar desatualizadas.
- [ ] Após o push, a Action "Deploy Pages" ficou verde e https://joseluizn.github.io/chuva-rio/ mostra a nova data.

## 7. Limitações conhecidas

- **Viés do ERA5**: reanálise em grade de ~0,25° (~28 km), não é pluviômetro. Superestima o volume e sobretudo a frequência de dias chuvosos em relação a Alerta Rio, INMET e Galeão (ver `docs/analise_modelos.md` e `docs/revisao_opus.md`). O site usa as estações apenas como contexto.
- **ERA5-Land vazio**: a API devolve apenas nulos para este ponto (testado também com `cell_selection=land` e outras coordenadas próximas), então não é usado.
- **`best_match` descontínuo em 2017**: muda internamente para ECMWF IFS, com queda de volume anual; por isso a série principal é o ERA5.
- **`ecmwf_ifs` só existe a partir de 2017**.
- **Nebulosidade do ERA5**: saída de modelo, não observação; sem referência observada conferida. O limiar de 30% é convencional (ver acima). A fração de insolação do ERA5 é quase constante no ano e foi descartada.
- **Atraso de ~5-6 dias** no ERA5: os últimos dias vêm nulos e são preenchidos nas atualizações seguintes. Valores provisórios (ERA5T) podem ser revisados semanas depois; a checagem de revisão ignora os últimos 60 dias, mas dias com 60 a ~90 dias podem ainda mudar um pouco.
- **Mudanças de versão da reanálise** podem alterar o histórico inteiro; é para isso que existe a validação.
- **Licença e atribuição**: ver seção 8.
- **Não foi possível testar daqui** a chamada real à API (inclusive a da nebulosidade, só exercitada com respostas simuladas) nem a execução real das Actions (ambiente sem rede); os testes usam respostas simuladas. A primeira execução real deve ser feita com `--dry-run` e, no GitHub, via "Run workflow".

## 8. Licença, atribuição e limites de uso do Open-Meteo

Registrado a partir de https://open-meteo.com/en/terms e https://open-meteo.com/en/licence (consultadas em 2026-11-12):

- Os dados da API são fornecidos sob **CC BY 4.0**: é preciso dar crédito, linkar a licença e indicar se houve alterações. Exemplo de crédito da própria Open-Meteo: "Weather data by Open-Meteo.com" com link para https://open-meteo.com/. Pesquisadores são incentivados a citá-la (a página de licença traz APA, MLA, Harvard e BibTeX).
- Os dados de reanálise vêm do Copernicus Climate Change Service (C3S/ECMWF), com licença própria do Copernicus; os dados do ECMWF IFS constam como CC BY. Cada provedor tem sua licença; confira a página de licença.
- API gratuita: **uso não comercial**; limites por IP/aplicação de 600 chamadas/min, 5.000/hora, 10.000/dia e 300.000/mês. Uso abusivo pode ser bloqueado sem aviso. A página de termos não traz regras específicas para a Historical Weather API. Este projeto faz ~12 requisições por atualização.
- Os servidores compartilhados de CI (GitHub Actions) podem atingir limites por IP antes; se houver HTTP 429, rode de novo mais tarde.
- O site deve manter a atribuição visível ("Dados: Open-Meteo.com, CC BY 4.0; reanálise ERA5, Copernicus/ECMWF") e indicar que os dados foram agregados/processados.
