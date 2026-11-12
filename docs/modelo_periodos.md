# Quando chove menos (e quando o céu abre) entre abril e outubro

Modelo por decêndio (dias 1–10, 11–20, 21–fim de cada mês; 21 períodos de abr 1–10 a out 21–31) para o Rio de Janeiro.
Script: `scripts/model_periods.py` (só biblioteca padrão, sementes fixas, idempotente). Saída: `data/derived/periodos_abr_out.json`.
Números abaixo: execução com dados até 2026-11-05 (chuva e nuvem); anos completos 1995–2025 (31 anos); 2026 fica fora da estimação.

## Em linguagem simples: quando o tempo é bom

Cada mês de abril a outubro foi dividido em três períodos (os decêndios): início (dias 1–10), meados (11–20) e fim (21 ao fim do mês). "Tempo bom" tem quatro versões: **dia bom** (céu aberto e sem chuva), **céu aberto**, **sem chuva** (< 1 mm) e **sem chuva forte** (< 5 mm); em todas, mais é melhor.

**Como medimos a incerteza.** Refizemos a conta 1.000 vezes, cada vez com 31 anos sorteados (com repetição) entre 1995 e 2025, como se tivéssemos 1.000 históricos alternativos. "Melhor em 70% das simulações" quer dizer em 700 desses 1.000. As chances viram palavras na escala de probabilidade do IPCC (Mastrandrea et al. 2010), usando sempre o termo mais específico:

| Termo | Chance |
|---|---|
| praticamente certo | 99% ou mais |
| muito provável | 90% ou mais |
| provável | 66% ou mais |
| tão provável quanto improvável | 33% a 66% |
| improvável | menos de 33% |
| muito improvável | menos de 10% |
| excepcionalmente improvável | menos de 1% |

As chances medem só a variação entre anos dentro da reanálise; não incluem os erros do ERA5.

- **Dia bom.** O melhor período vai do início de junho ao início de setembro: **praticamente certo** (mais de 99%). Dentro dessa faixa nenhum período se destaca claramente. No pico da curva sazonal, fim de julho (jul 21–31), são cerca de 5 dias bons em 11; estar entre os 3 melhores é **provável** (69%), mas ser exatamente o melhor é **improvável** (21%). O período que mais vezes fica em 1º nos dados é o início de julho (35%, **tão provável quanto improvável**). O pior está no início de abril ou na segunda metade de outubro (**praticamente certo**); no fim de outubro, cerca de 1 dia bom em 11.
- **Céu aberto.** Mesmo desenho: o melhor período vai de meados de junho ao início de setembro (**praticamente certo**); pico em fim de julho, cerca de 5 dias de céu aberto em 11; entre os 3 melhores, **provável** (73%); o 1º exato é **improvável** para qualquer período.
- **Sem chuva.** O melhor período vai do fim de maio ao início de setembro (**praticamente certo**); em meados de julho são cerca de 8 dias sem chuva em 10 (no ERA5; na realidade, mais). Para meados de julho, estar entre os 3 melhores é **improvável** (31%): a faixa seca é larga e plana.
- **Sem chuva forte.** O melhor período vai do início de maio ao início de setembro (**praticamente certo**). Aqui um período se aproxima de vencer: meados de junho é o melhor em 58% das simulações (**tão provável quanto improvável**).

**Em uma frase:** de junho ao início de setembro o tempo bom é muito mais comum do que em abril ou outubro, e isso é praticamente certo; qual semana exata dentro dessa faixa é a melhor, os dados não dizem.

Os números acima são da execução com dados até 2026-11-05; a página `site/modelo.html` recalcula todos a cada atualização.

## A resposta em poucas palavras (versão técnica)

**Chuva.** A estação mais seca do ano no Rio vai, grosso modo, de **meados de junho a meados de agosto**. O centro dessa janela, segundo o modelo sazonal, é **jul 11–20**: chance de ~23% de um dia com chuva ≥ 1 mm, ou ~2,3 dias chuvosos em 10. Mas o fundo da curva é **plano**: de jun 11–20 a ago 11–20 todos os decêndios ficam entre 21% e 24% (dados brutos), e nenhum deles se separa dos vizinhos além do ruído entre anos. Escolher "jul 11–20" em vez de "jun 21–30" ou "ago 1–10" não é uma decisão que os dados sustentem; escolher **julho em vez do início de abril ou do fim de outubro** (mais de 50% de dias com chuva) é; maio e setembro ficam no meio (29–44%).

- Confiança no *centro* da estação seca (modelo suave): jul 11–20 é o mínimo em 98% das réplicas bootstrap, e em 84–87% em cada metade da série (1995–2010 e 2011–2025).
- Confiança num *decêndio específico* (sem impor forma): nenhum passa de 30%. jul 21–31 (29%), jun 21–30 (24%), ago 1–10 (18%) e jul 11–20 (10%) juntos cobrem 80% das réplicas.
- Para chuva mais forte (≥ 5 mm), o centro do modelo é o mesmo (jul 11–20), mas os dados brutos favorecem **jun 11–20** (6% dos dias, P(melhor) sem forma = 58%; está no top 3 em 97% das réplicas). Se a pergunta é "evitar chuva que atrapalha", a segunda quinzena de junho é tão boa quanto julho, possivelmente melhor.

**Céu aberto.** Dia aberto = nuvem média diurna (09–17 h) ≤ 30%, a classe "clear" do NOAA/NCEI (0 a 3/10 de céu coberto); 32% dos dias de abr–out. O pico vem um pouco depois do mínimo de chuva: o modelo coloca o centro em **jul 21–31** (~47% dos dias abertos, ~5,1 em 11 dias; P(melhor) 89%). De novo há um platô, mais longo: de jun 11–20 a set 1–10 a fração bruta fica em 39–46%, sem diferença distinguível do ruído. Sem impor forma, o P(melhor) se espalha (jul 1–10 35%, jul 21–31 24%, ago 1–10 12%). Outubro é o pior período para céu aberto (13–18%).

**Dia bom (aberto e sem chuva ≥ 1 mm).** Praticamente igual ao aberto: centro em **jul 21–31** (~46%, P(melhor) 90%; sem impor forma, jul 1–10 35%, jul 21–31 21%), platô de meados de junho ao início de setembro.

**Em uma frase:** julho é a aposta; dentro de julho, a primeira metade é um pouco mais seca e a segunda um pouco mais aberta, mas essas diferenças estão dentro do ruído. Entre meados de junho e meados de agosto, nenhum decêndio se distingue estatisticamente dos vizinhos.

## 1. Dados e desfechos

- **Chuva**: `data/daily/era5.csv`, ERA5 via Open-Meteo, célula -22,75/-43,25. Ver `docs/analise_modelos.md` para a escolha do ERA5: é a única série homogênea 1995–hoje, mas tem viés úmido (~+30% de volume e ~+80% de dias ≥ 1 mm frente a observações) e exagera o contraste sazonal.
- **Desfechos diários**: chuvoso = `precip_mm ≥ 1,0`; sensibilidade com ≥ 5 mm (e 0,5, 2, 10 mm). Aberto = nuvem diurna (09–17 h) ≤ 30% (`common.OPEN_THR`, "clear" do NOAA/NCEI); "bom" = aberto **e** < 1 mm (seção 5).
- **Nuvem**: `data/daily/era5_cloud.csv`, mesma célula ERA5.
- **Anos**: só anos civis completos (1995–2025). O ano corrente (parcial) é excluído da estimação para não pesar só os meses já ocorridos.

## 2. Método

**Base descritiva.** Por decêndio: proporção agregada de dias com o desfecho e IC 90% de Wilson (Wilson 1927). O IC de Wilson supõe dias independentes e é **estreito demais** aqui (abaixo); por isso o JSON traz também o IC 90% por bootstrap de anos (`p_raw_boot90`) e a distribuição ano a ano (`year_share_quartiles`, `year_share_by_year`).

**Dependência entre dias.** Dias chuvosos vêm em sequências: em abr–out, P(chuva | ontem choveu) = 59% contra P(chuva | ontem seco) = 20%. A variância das contagens anuais por decêndio é, na mediana, 1,7 vez a binomial (faixa 1,1–2,5). Tratar os ~310 dias de cada decêndio como independentes superestimaria a precisão em ~30% no desvio-padrão.

**Modelo sazonal.** Regressão logística da probabilidade diária no dia do ano com *K* pares de Fourier,

$$\operatorname{logit} p(t) = \beta_0 + \sum_{k=1}^{K} \left[a_k \cos\frac{2\pi k t}{366} + b_k \sin\frac{2\pi k t}{366}\right],$$

ajustada no **ano inteiro** (para que abril e outubro não sejam bordas livres) por Newton/IRLS em dados agregados por dia do calendário (o preditor só depende do dia, então contagens por dia são estatística suficiente). A probabilidade do decêndio é a média das probabilidades diárias nos seus dias.

**Escolha de K.** Validação cruzada deixando um ano de fora (31 dobras), log-loss avaliada só nos dias abr–out; escolhemos o menor *K* a até 1 erro-padrão (entre anos) do mínimo (regra de 1 EP, Hastie, Tibshirani & Friedman 2009, §7.10 — a regra é julgamento meu, para não perseguir ruído). Resultado para chuva ≥ 1 mm:

| K | parâmetros | log-loss CV (abr–out) | AIC | BIC |
|---|---|---|---|---|
| 0 | 1 | 0,6729 | 15.645 | 15.652 |
| **1** | 3 | **0,6140** | 14.223 | **14.245** |
| 2 | 5 | 0,6142 | 14.212 | 14.248 |
| 3 | 7 | 0,6144 | 14.210 | 14.262 |
| 4 | 9 | 0,6145 | 14.204 | 14.270 |
| 6 | 13 | 0,6143 | 14.194 | 14.289 |
| proporção bruta por decêndio | 21 | 0,6168 | — | — |

K = 1 é o mínimo da validação cruzada **e** do BIC. O AIC prefere K = 6, mas o AIC trata os ~11.300 dias como independentes e, com a persistência acima, penaliza pouco a complexidade. O que decide: harmônicos extras e médias por decêndio **não preveem melhor um ano novo** do que uma senoide única. Ou seja, a "forma fina" dentro da estação seca não se repete de um ano para o outro. Com ≥ 5 mm a conclusão é a mesma (K = 1).

**Incerteza.** Bootstrap em blocos de **anos inteiros** (1.000 réplicas, semente 20261112): cada réplica sorteia 31 anos com reposição, reajusta o modelo e recalcula as proporções brutas. Reamostrar anos preserva a persistência dentro do ano (bootstrap de blocos: Künsch 1989; bootstrap percentil: Efron & Tibshirani 1993). Para cada decêndio: IC 90% percentil, P(melhor) = fração das réplicas em que ele é o mais seco, P(top 3), e a diferença pareada para o melhor.

**Duas leituras do ranking (importante).** Com K = 1 a curva é uma senoide: o mínimo é único e o modelo só pode errar a *posição* dele. Logo, o P(melhor) do modelo mede a incerteza sobre **o centro da estação seca**, não sobre qual decêndio específico é mais seco. Para a segunda pergunta usamos o P(melhor) **sem forma** (proporções brutas por decêndio, mesmas réplicas). O JSON traz as duas (`P_best`, `P_best_raw`) e o P(melhor) do modelo com K = 1…4 (`P_best_by_K`): quanto mais flexível a curva, mais o P(melhor) se espalha (K = 3: jul 11–20 49%, jul 21–31 28%, jul 1–10 20%; K = 4: jul 21–31 69%, ago 1–10 23%). "Dentro do ruído" (`within_noise_of_best`) usa as diferenças brutas pareadas.

## 3. Resultados: chuva ≥ 1 mm

Negrito = mínimo do modelo. "Dias esperados" = probabilidade do modelo × dias do decêndio (10 ou 11; decêndios de 11 dias têm mais dias esperados com a mesma chance diária). Chuva média = total médio do ERA5 no período (lembre do viés úmido do ERA5 em volume; ver seção 6).

| Decêndio | bruto (Wilson 90%) | bruto, IC bootstrap anos | modelo (IC 90%) | dias chuvosos esperados | P(melhor) modelo | P(melhor) sem forma | P(top 3) sem forma | chuva média no período, mm (IC 90%) |
|---|---|---|---|---|---|---|---|---|
| abr 1–10 | 57% (52–62) | 51–64 | 50% (48–52) | 5,0 | 0% | 0% | 0% | 49 (40–61) |
| abr 11–20 | 38% (33–42) | 32–44 | 45% (43–47) | 4,5 | 0% | 0% | 0% | 28 (22–35) |
| abr 21–30 | 39% (35–44) | 32–46 | 41% (39–43) | 4,1 | 0% | 0% | 0% | 28 (22–35) |
| mai 1–10 | 35% (31–40) | 30–41 | 37% (35–39) | 3,7 | 0% | 0% | 0% | 22 (17–27) |
| mai 11–20 | 38% (34–43) | 32–45 | 33% (31–35) | 3,3 | 0% | 0% | 0% | 25 (19–31) |
| mai 21–31 | 29% (25–34) | 24–34 | 30% (28–31) | 3,3 | 0% | 0% | 1% | 23 (19–28) |
| jun 1–10 | 29% (25–33) | 24–34 | 27% (26–29) | 2,7 | 0% | 0% | 1% | 18 (14–23) |
| jun 11–20 | 24% (20–28) | 20–28 | 25% (24–27) | 2,5 | 0% | 3% | 21% | 12 (9–15) |
| jun 21–30 | 21% (18–25) | 17–25 | 24% (23–25) | 2,4 | 0% | 24% | 62% | 13 (10–16) |
| jul 1–10 | 23% (20–27) | 18–28 | 23% (22–25) | 2,3 | 2% | 8% | 31% | 15 (11–20) |
| **jul 11–20** | 24% (20–28) | 19–29 | 23% (22–24) | 2,3 | 98% | 10% | 30% | 15 (10–21) |
| jul 21–31 | 21% (18–25) | 17–26 | 23% (22–25) | 2,6 | 0% | 29% | 67% | 14 (10–17) |
| ago 1–10 | 23% (19–27) | 18–28 | 24% (23–26) | 2,4 | 0% | 18% | 44% | 14 (10–18) |
| ago 11–20 | 24% (20–28) | 19–29 | 26% (24–27) | 2,6 | 0% | 6% | 28% | 12 (9–15) |
| ago 21–31 | 26% (23–30) | 22–31 | 28% (26–30) | 3,1 | 0% | 0% | 7% | 21 (15–27) |
| set 1–10 | 26% (23–31) | 21–32 | 31% (29–33) | 3,1 | 0% | 1% | 8% | 19 (13–24) |
| set 11–20 | 34% (29–38) | 28–39 | 34% (32–36) | 3,4 | 0% | 0% | 0% | 26 (20–32) |
| set 21–30 | 44% (39–48) | 38–50 | 38% (36–40) | 3,8 | 0% | 0% | 0% | 33 (26–39) |
| out 1–10 | 48% (43–52) | 41–55 | 42% (40–44) | 4,2 | 0% | 0% | 0% | 38 (31–47) |
| out 11–20 | 46% (41–50) | 39–54 | 47% (45–49) | 4,7 | 0% | 0% | 0% | 41 (33–49) |
| out 21–31 | 54% (49–58) | 49–58 | 52% (49–54) | 5,7 | 0% | 0% | 0% | 49 (38–59) |

Leitura:

- **O que é sólido**: de jun 11–20 a ago 11–20 a chance diária de chuva fica em ~21–24% (brutos), contra 45–57% no início de abril e no fim de outubro. Isso aparece no modelo, nos dados brutos, nas duas metades da série e em todos os limiares.
- **O que é ruído**: a ordem *dentro* desse platô. A diferença bruta entre jul 11–20 e qualquer decêndio de mai 21–31 a set 1–10 tem IC 90% que inclui zero (pareado, bootstrap de anos). Num ano qualquer, a fração de dias chuvosos num decêndio de julho varia de 0% a 50–60% (quartis 10%–40%): a variação entre anos é muito maior que a diferença entre decêndios vizinhos.
- **Desvio do modelo nas pontas**: abr 1–10 (57% bruto) fica acima da curva (50%) e abr 11–20 abaixo; o início de abril ainda é cauda do verão. Uma senoide não captura essa queda brusca, mas isso não afeta o fundo da estação seca.
- **Volume**: o menor total médio está em jun 11–20 e ago 11–20 (~12 mm em 10 dias, valores ERA5), seguido de jun 21–30 e jul.

## 4. Robustez (chuva)

| Verificação | Top 3 do modelo | Observação |
|---|---|---|
| Série completa, ≥ 1 mm, K = 1 | jul 11–20, jul 1–10, jul 21–31 | — |
| 1995–2010 (16 anos) | jul 11–20, jul 1–10, jul 21–31 | P(melhor): jul 11–20 87%, jul 1–10 12%. Top 3 bruto: ago 11–20, jun 11–20, jun 1–10 |
| 2011–2025 (15 anos) | jul 11–20, jul 1–10, jul 21–31 | P(melhor): jul 11–20 84%, jul 1–10 9%, jul 21–31 7%. Top 3 bruto: jun 21–30, jul 21–31, jul 11–20 |
| ≥ 0,5 mm | jul 11–20, jul 21–31, jul 1–10 | Spearman com ≥ 1 mm: 0,999 |
| ≥ 2 mm | jul 11–20, jul 1–10, jul 21–31 | Spearman 1,00 |
| ≥ 5 mm (K escolhido = 1) | jul 11–20, jul 1–10, jul 21–31 | Modelo: P(melhor) jul 11–20 75%, jul 1–10 25%. **Sem forma: jun 11–20 58%, jun 21–30 25%** |
| ≥ 10 mm | jul 11–20, jul 1–10, jul 21–31 | Spearman 0,99 |
| K = 2 | jul 11–20, jul 21–31, jul 1–10 | Spearman com K = 1: 0,996 |
| Galeão (GHCN, observação) | jun 21–30, mai 1–10, jul 1–10 | Spearman com ERA5 bruto 0,74; ver abaixo |

- **Metades da série**: o centro da estação seca (modelo) não muda; o ranking bruto muda bastante entre as metades, o que confirma que a ordem fina dentro do platô é ruído.
- **Viés do ERA5 (chuva fraca)**: o ERA5 inventa muitos dias de chuva fraca. Se esse viés fosse sazonalmente desigual, o ranking com ≥ 1 mm poderia ser artefato. Com ≥ 5 mm (menos sensível a garoa espúria), o modelo mantém o mesmo centro e o mesmo ordenamento (Spearman 1,00), e os níveis caem para ~9–10% no platô. O viés afeta **níveis**, não a forma; a única mudança é que, sem impor forma, a segunda quinzena de junho aparece como a de menos chuva forte.
- **Galeão (observação independente)**: a estação GHCN BRM00083746 tem só ~29% dos dias em 1995–2025 (~75–110 dias por decêndio, anos irregulares, lacunas possivelmente não aleatórias). Mesmo assim: níveis bem menores (7–19% de dias ≥ 1 mm de jun 11–20 a ago 11–20, contra 21–26% no ERA5, coerente com o viés de frequência), mesmo formato geral (Spearman 0,74 com o ERA5 bruto) e o decêndio mais seco é jun 21–30 (7%), dentro do platô. É checagem de forma, não de nível.

## 5. Céu aberto e "dia bom"

**Dados.** `data/daily/era5_cloud.csv` (mesma célula ERA5 da chuva): cobertura total de nuvens média de 24 h (`cloud_cover_mean_pct`), média das horas 09–17 locais (`cloud_daytime_0917_pct`), insolação e duração do dia (minutos). Ver `data/daily/meta.json` (`cloud`).

**Definição (padrão do site).** Dia **aberto** = cobertura média **diurna (09–17 h) ≤ 30%**. O limiar vem de `scripts/common.py` (`OPEN_THR = 30.0`) e corresponde à classe **"clear"** (0 a 3/10 de céu coberto, média das horas de luz) do *Comparative Climatic Data* do NOAA/NCEI. Um limiar de ≤ 3 oktas (37,5%) já inclui nuvens esparsas e não é "céu limpo" em nenhuma das duas convenções; ele fica como teste de robustez. Dia **bom** = aberto **e** chuva < 1 mm. Em abr–out, 32% dos dias são abertos por essa definição (37% com 37,5%).

**Escolha de K.** Para nuvem há mais forma que para chuva: K = 2 melhora claramente a log-loss CV sobre K = 1 (0,6028 vs 0,6066); K maiores melhoram pouco (mínimo em K = 6, 0,6020, dentro de 1 EP de K = 2). O BIC também escolhe K = 2. Escolhido: K = 2 para aberto e para bom.

### Aberto (nuvem diurna ≤ 30%)

| Decêndio | bruto (Wilson 90%) | bruto IC bootstrap anos | modelo (IC 90%) | dias abertos esperados | P(melhor) modelo | P(melhor) sem forma | P(top 3) sem forma |
|---|---|---|---|---|---|---|---|
| abr 1–10 | 17% (14–21) | 13–21 | 22% (20–25) | 2,2 | 0% | 0% | 0% |
| abr 11–20 | 24% (20–28) | 18–30 | 23% (21–26) | 2,3 | 0% | 0% | 0% |
| abr 21–30 | 34% (30–39) | 27–41 | 24% (21–27) | 2,4 | 0% | 0% | 1% |
| mai 1–10 | 31% (27–35) | 25–37 | 26% (23–29) | 2,6 | 0% | 0% | 0% |
| mai 11–20 | 24% (20–28) | 18–30 | 28% (25–31) | 2,8 | 0% | 0% | 0% |
| mai 21–31 | 28% (24–32) | 22–34 | 31% (28–34) | 3,4 | 0% | 0% | 0% |
| jun 1–10 | 37% (32–41) | 30–44 | 34% (31–37) | 3,4 | 0% | 0% | 3% |
| jun 11–20 | 41% (36–45) | 35–47 | 38% (35–41) | 3,8 | 0% | 6% | 16% |
| jun 21–30 | 39% (34–43) | 33–45 | 41% (39–44) | 4,1 | 0% | 0% | 5% |
| jul 1–10 | 46% (41–50) | 39–52 | 44% (42–47) | 4,4 | 0% | 35% | 66% |
| jul 11–20 | 42% (37–46) | 36–47 | 46% (44–48) | 4,6 | 7% | 5% | 25% |
| **jul 21–31** | 46% (41–50) | 41–50 | 47% (44–49) | 5,1 | 89% | 24% | 73% |
| ago 1–10 | 43% (39–48) | 37–49 | 46% (43–48) | 4,6 | 4% | 12% | 39% |
| ago 11–20 | 39% (35–44) | 33–45 | 43% (41–46) | 4,3 | 0% | 2% | 7% |
| ago 21–31 | 43% (39–48) | 38–49 | 39% (37–42) | 4,3 | 0% | 8% | 37% |
| set 1–10 | 42% (37–47) | 35–49 | 34% (31–37) | 3,4 | 0% | 8% | 28% |
| set 11–20 | 31% (27–35) | 24–38 | 29% (26–31) | 2,9 | 0% | 0% | 0% |
| set 21–30 | 22% (18–26) | 16–27 | 23% (21–26) | 2,3 | 0% | 0% | 0% |
| out 1–10 | 18% (15–22) | 13–24 | 19% (17–21) | 1,9 | 0% | 0% | 0% |
| out 11–20 | 13% (10–16) | 8–18 | 15% (13–17) | 1,5 | 0% | 0% | 0% |
| out 21–31 | 13% (10–16) | 9–16 | 12% (11–14) | 1,4 | 0% | 0% | 0% |

### Bom (aberto e < 1 mm)

| Decêndio | bruto (Wilson 90%) | bruto IC bootstrap anos | modelo (IC 90%) | dias bons esperados | P(melhor) modelo | P(melhor) sem forma | P(top 3) sem forma |
|---|---|---|---|---|---|---|---|
| abr 1–10 | 15% (12–19) | 11–19 | 20% (17–22) | 1,9 | 0% | 0% | 0% |
| abr 11–20 | 21% (17–25) | 15–27 | 21% (18–23) | 2,1 | 0% | 0% | 0% |
| abr 21–30 | 32% (28–37) | 25–39 | 22% (19–25) | 2,2 | 0% | 0% | 0% |
| mai 1–10 | 29% (25–33) | 23–35 | 24% (21–27) | 2,4 | 0% | 0% | 0% |
| mai 11–20 | 22% (18–26) | 16–28 | 26% (23–29) | 2,6 | 0% | 0% | 0% |
| mai 21–31 | 26% (23–30) | 21–32 | 29% (27–32) | 3,2 | 0% | 0% | 0% |
| jun 1–10 | 36% (32–41) | 29–43 | 33% (30–36) | 3,3 | 0% | 0% | 4% |
| jun 11–20 | 39% (35–44) | 33–46 | 37% (34–39) | 3,7 | 0% | 5% | 15% |
| jun 21–30 | 38% (33–42) | 32–44 | 40% (37–43) | 4,0 | 0% | 0% | 5% |
| jul 1–10 | 45% (40–50) | 38–51 | 43% (40–46) | 4,3 | 0% | 35% | 64% |
| jul 11–20 | 41% (36–46) | 35–47 | 45% (43–48) | 4,5 | 5% | 6% | 27% |
| **jul 21–31** | 45% (40–49) | 39–50 | 46% (43–48) | 5,0 | 90% | 21% | 69% |
| ago 1–10 | 42% (37–47) | 36–48 | 45% (43–47) | 4,5 | 6% | 11% | 35% |
| ago 11–20 | 38% (34–43) | 32–45 | 43% (40–45) | 4,3 | 0% | 2% | 9% |
| ago 21–31 | 43% (39–48) | 38–49 | 39% (36–41) | 4,2 | 0% | 13% | 49% |
| set 1–10 | 40% (36–45) | 33–48 | 33% (31–36) | 3,4 | 0% | 6% | 22% |
| set 11–20 | 30% (26–34) | 24–37 | 28% (26–31) | 2,8 | 0% | 0% | 0% |
| set 21–30 | 21% (18–25) | 16–26 | 23% (20–25) | 2,3 | 0% | 0% | 0% |
| out 1–10 | 18% (15–22) | 13–23 | 18% (16–20) | 1,8 | 0% | 0% | 0% |
| out 11–20 | 12% (10–16) | 8–17 | 14% (13–16) | 1,4 | 0% | 0% | 0% |
| out 21–31 | 11% (9–15) | 8–15 | 11% (10–13) | 1,3 | 0% | 0% | 0% |

Leitura:

- **Centro**: o máximo de céu aberto vem um pouco depois do mínimo de chuva: **jul 21–31** (modelo: ~47% de dias abertos, ~5,1 em 11 dias; P(melhor) 89%, com jul 11–20 em 7% e ago 1–10 em 4%). Para "dia bom" o resultado é praticamente o mesmo, porque dias abertos quase nunca têm chuva ≥ 1 mm: jul 21–31, ~46%, P(melhor) 90%.
- **Platô**: de jun 11–20 a set 1–10 a fração bruta de dias abertos fica entre 39% e 46%, e nenhum decêndio desse trecho se distingue de jul 21–31 além do ruído (diferenças pareadas por bootstrap; a única exceção é jun 1–10 para "bom", que também entra). Sem impor forma, o P(melhor) se espalha: jul 1–10 35%, jul 21–31 24%, ago 1–10 12%, set 1–10 8%, ago 21–31 8%, jun 11–20 6%. O platô de céu aberto avança mais pelo fim de agosto e início de setembro do que o platô seco.
- **K importa no detalhe**: com K = 1 o centro iria para jul 1–10 (84%); com K = 3 para ago 1–10 (58%); com K = 4 fica dividido entre ago 1–10 (44%) e jul 21–31 (40%). A posição exata do pico (do início de julho ao início de agosto) depende da forma assumida; o platô não.
- **Abril–maio**: há uma janela secundária em abr 21–mai 10 (31–34% de dias abertos, brutos) que a curva com K = 2 suaviza, seguida de queda em mai 11–20 (24%). Pode ser ruído (os ICs são largos) ou um padrão real; não testei.
- **Outubro** é o pior período para céu aberto (13–18%), pior que abril.

### Robustez (aberto)

| Verificação | Top 3 do modelo | % dos dias abr–out | Spearman com o principal |
|---|---|---|---|
| Principal: diurna ≤ 30% ("clear" NOAA), K = 2 | jul 21–31, jul 11–20, ago 1–10 | 32% | — |
| Diurna ≤ 25% | jul 21–31, ago 1–10, jul 11–20 | 29% | 0,995 |
| Diurna ≤ 37,5% (≤ 3 oktas) | jul 21–31, jul 11–20, ago 1–10 | 37% | 0,991 |
| Diurna ≤ 50% (≤ 4 oktas) | jul 11–20, jul 1–10, jul 21–31 | 47% | 0,93 |
| Média de 24 h ≤ 30% | jul 21–31, ago 1–10, jul 11–20 | — | 0,992 |
| 1995–2010 | jul 21–31, jul 11–20, ago 1–10 | — | 0,99 |
| 2011–2025 | jul 21–31, ago 1–10, jul 11–20 | — | 0,98 |
| Insolação/duração do dia ≥ 0,6 | abr 1–10, abr 11–20, abr 21–30 | 81% | 0,09 |
| Insolação, limiar casado por quantil (≥ 0,93) | abr 1–10, abr 11–20, out 1–10 | 32% | −0,88 |

Com o limiar antigo (37,5%) a resposta era a mesma (centro jul 21–31, P(melhor) 69%, platô jun 11–20 a set 1–10 com 43–49% brutos); o limiar mais estrito baixa os níveis em ~3–7 p.p. e concentra o P(melhor) do modelo em jul 21–31.

**A insolação do ERA5 não serve aqui.** A fração de insolação (`sunshine_min / daylight_min`; definição OMM: irradiância direta > 120 W/m²) é quase constante ao longo do ano (0,70–0,83 nas médias mensais), enquanto a nebulosidade diurna vai de 44% (julho) a 75% (novembro). Mesmo em meses com 70% de nuvem a fração passa de 0,7, e em dias com ≤ 10% de nuvem ela fica em 0,92–0,98. Com o limiar 0,6, 81% dos dias de abr–out seriam "abertos" e o ranking não tem relação com o de nuvem (Spearman 0,09). Mesmo escolhendo o limiar para dar a mesma fração de dias abertos (≥ 0,93, 32%), o ranking se **inverte** (Spearman −0,88): abril e outubro passam a parecer os mais ensolarados. A insolação não acompanha a nuvem do próprio ERA5. Minha leitura, não verificada: a insolação do Open-Meteo é derivada da radiação de um modo que satura com nuvem parcial ou fina, e o que sobra de variação reflete a geometria solar (altura do sol, duração do dia) mais que a nebulosidade. Por isso ela fica de fora da conclusão.

## 6. Ressalvas

- **Nuvem do ERA5 não foi validada** contra observação (p. ex. METAR/SYNOP do Galeão ou do Santos Dumont). Reanálises costumam errar nuvens baixas (estratocúmulos costeiros, nevoeiro de inverno na baía) ; um erro desse tipo deslocaria sobretudo os níveis e, menos provavelmente, a posição do pico.
- **Reanálise, não observação.** ERA5 é modelo assimilando observações, em célula de ~25 km (-22,75/-43,25, ao norte do centro, perto do Galeão/Baía de Guanabara). O Rio tem forte variação espacial (maciços, orla, Zona Oeste): a Zona Sul e a serra podem ter outra sazonalidade de chuva e nebulosidade.
- **Viés de nível.** ERA5 superestima o volume (~+30% vs Alerta Rio) e muito a frequência de dias ≥ 1 mm (~+80% vs Galeão). As probabilidades absolutas acima (23% em julho) são altas demais; o Galeão sugere algo como 10–15%. Use o JSON para **comparar períodos**, não como previsão de chance absoluta. A análise anterior também indica que o ERA5 subestima o volume de abr–ago frente ao Alerta Rio; se isso valer para a frequência, o contraste real entre abril/outubro e julho seria menor do que o modelo mostra, mas a posição do mínimo não deveria mudar.
- **Persistência.** Dias chuvosos vêm em sequência, então "2,3 dias esperados em 10" não implica 2–3 dias espalhados: em muitos anos o decêndio inteiro é seco e em outros chove 4–6 dias seguidos (ver `year_share_by_year`).
- **Estacionariedade.** O modelo supõe a mesma sazonalidade em 1995–2025. As duas metades dão o mesmo centro, mas 31 anos não excluem mudança de regime recente.
- **Climatologia ≠ previsão.** Para um ano específico, ENSO e a previsão sazonal do INMET/CPTEC dizem mais do que a média de 31 anos.

## 7. O que mudaria a conclusão

- Uma série observada longa e completa (Alerta Rio por estação, INMET A652/A621) com outro centro da estação seca. O Galeão, com lacunas, aponta para o mesmo platô.
- Um ponto de grade diferente (Zona Sul, Barra, serra) se a sazonalidade local diferir.
- Mais anos que tornem o padrão fino reprodutível: hoje harmônicos extras não melhoram a previsão de um ano novo; se passarem a melhorar, K sobe e o P(melhor) do modelo se espalha (ver `P_best_by_K`).
- Para chuva forte, uma confirmação observada de que a 2ª quinzena de junho é de fato mais seca que julho.

## 8. Reexecução

```bash
python3 scripts/model_periods.py            # 1.000 réplicas, ~2 min (chuva + nuvem)
python3 scripts/model_periods.py --boot 200 # mais rápido, para testes
```

O resultado só muda quando os dados mudam (`meta.generated_at` = última data com dado). Duas execuções seguidas produzem JSON idêntico.

### Estrutura do JSON (para gráficos)

- `meta.decendio_keys`, `meta.decendio_labels`: eixo x (21 períodos).
- `outcomes.<rain|rain_ge5mm|open|bom>.decendios[]`: `p_raw` + `p_raw_boot90` (ponto e barra de erro), `p_model` + `p_model_boot90`, `P_best`, `P_best_raw`, `P_top3`, `P_top3_raw`, `expected_days`, `year_share_by_year`, e (só chuva) `mean_mm_window`.
- `outcomes.<...>.best_point` (para destacar), `daily_curve` (214 probabilidades diárias de 1/abr a 31/out, para a linha do modelo), `within_noise_of_best`, `set_covering_80pct_P_best[_raw]`, `P_best_by_K`, `model_selection`.
- `robustness`: subamostras, limiares, K alternativo, Galeão.
- `outcomes.<...>.decendios[]` também traz a distribuição de postos (`rank_dist_model`, `rank_dist_raw`: P(posto = k), k = 1…21, 1 = melhor; `rank_median_*`, `rank_ci90_*`), o grupo (`tier`: 1 = sem diferença distinguível do melhor, 2 = intermediário, 3 = sem diferença do pior; `tier_ambiguous`) e `raw_diff_vs_worst[_boot90]`.
- `outcomes.<...>.pairwise`: matrizes 21 × 21 (linha i contra coluna j) com `P_better_raw` e `P_better_model` (fração das réplicas em que i foi melhor que j; empate conta 0,5), `diff_raw` e `diff_raw_ci90` (diferença bruta pareada i − j e faixa de 90%) e `ci_excludes_zero`.
- `outcomes.<...>.per_year`: contagens por ano × decêndio (`count`, `n`; inclui o ano parcial, marcado em `partial_year`, que não entra em nenhuma estimativa) e `good`: fração dos anos completos em que o decêndio foi "bom", com faixa de Wilson de 90%.
- `outcomes.<...>.calibration`: previsto (com todos os anos e deixando o ano de fora) × observado por decêndio.
- `meta.diagnostics`: por desfecho, tabela de K (log-loss CV ± EP entre anos, diferença para o mínimo ± EP, AIC, BIC) e calibração; `robustness_rows` resume subamostras, limiares, nuvem de 24 h, insolação e Galeão com top 3 e Spearman.

### Ranking, grupos e anos bons (regras)

- **Empates.** Nas proporções brutas, dois decêndios de 10 dias com a mesma contagem numa réplica empatam. Desde esta versão, empates são desfeitos ao acaso (semente fixa) em vez de favorecer o decêndio de índice menor; isso mudou os P(melhor) e P(top 3) sem forma em até ~4 p.p. (o maior caso: chuva ≥ 5 mm, jun 11–20, de 62% para 58%). Na comparação par a par, empate conta meio.
- **Grupos (`tier`).** Grupo 1: o melhor do modelo e os decêndios cuja diferença bruta pareada para ele tem faixa de 90% que não exclui que sejam tão bons. Grupo 3: o mesmo em relação ao pior do modelo. Grupo 2: o resto; quem cair nos dois grupos fica no 2 e é marcado `tier_ambiguous`. É uma regra de comparação com um único decêndio de referência, sem correção para comparações múltiplas (julgamento meu: a pergunta é "dá para dizer que é pior que o melhor?", e a regra responde de forma conservadora).
- **Anos bons.** Contagens absolutas no decêndio: chuva ≥ 1 mm, "até 2 dias chuvosos" e "nenhum dia chuvoso"; chuva ≥ 5 mm, "até 1 dia" e "nenhum dia"; céu aberto e dia bom, "5 ou mais" e "7 ou mais" dias. Decêndios de 11 dias têm um dia a mais (critério de chuva fica mais difícil; de céu aberto, mais fácil). Faixa de Wilson de 90% tratando os anos como independentes (julgamento: supõe que um ano não informa o seguinte, o que não testei).
- **Comparação de pares.** A página usa `pairwise` no confronto direto (dois períodos escolhidos) e na tabela "A contra os outros 20 períodos". "Diferença clara" = a faixa de 90% da diferença bruta pareada exclui zero. Pela curva sazonal quase todo par parece claramente diferente, porque a forma é imposta; os termos de probabilidade da página seguem os dados de cada período.

A página `site/modelo.html` (gerada por `scripts/build_model.py` a partir deste JSON) fala sempre em tempo bom: para chuva mostra a fração de dias **sem** chuva (1 − p; intervalos invertidos, diferenças com sinal trocado; P(melhor), postos e grupos não mudam, porque "melhor" no JSON já é "menos chuva"). O JSON não muda; a página principal continua lendo a chuva como está. Cada título traz o termo da escala acima, calculado a partir da chance correspondente: faixa do melhor (soma de P(melhor) nos períodos do grupo 1), faixa do pior (soma de P(último lugar) no grupo 3), estar entre os 3 melhores, vencer o confronto direto, e a fração dos anos em que o período foi bom.

## Referências

- Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. *JASA* 22(158), 209–212.
- Efron, B., & Tibshirani, R. J. (1993). *An Introduction to the Bootstrap*. Chapman & Hall.
- Künsch, H. R. (1989). The jackknife and the bootstrap for general stationary observations. *Annals of Statistics* 17(3), 1217–1241.
- Hastie, T., Tibshirani, R., & Friedman, J. (2009). *The Elements of Statistical Learning*, 2ª ed., §7.10 (validação cruzada e regra de 1 EP).
- NOAA/NCEI, *Comparative Climatic Data for the United States* (classes de céu: "clear" = 0 a 3/10 de cobertura média nas horas de luz).
- Mastrandrea, M. D. et al. (2010). *Guidance Note for Lead Authors of the IPCC Fifth Assessment Report on Consistent Treatment of Uncertainties*. IPCC.
- Hersbach, H. et al. (2020). The ERA5 global reanalysis. *QJRMS* 146, 1999–2049.

Julgamentos meus (não regra estabelecida): regra de 1 EP para K; usar diferenças brutas pareadas para "dentro do ruído"; usar a média diurna 09–17 h para "aberto" (o limiar de 30% é o padrão do site, `common.OPEN_THR`); descartar a insolação do ERA5; 1995 como início (herdado do projeto).
