# Análise de modelos Open-Meteo (Rio de Janeiro, precipitation_sum diária)

Acesso: 2026-11-12. Série 1995-01-01 a 2026-11-11 (11.638 dias). 2026 é ano parcial (até 11/11) e fica fora das comparações anuais.

## 1. Total anual (mm) por modelo

| Ano | best_match | era5 | ecmwf_ifs | era5_land | bm - era5 |
|---|---|---|---|---|---|
| 1995 | 2,110.0 | 2,110.0 | n/d | n/d | 0.0 |
| 1996 | 1,948.3 | 1,948.3 | n/d | n/d | 0.0 |
| 1997 | 1,558.6 | 1,558.6 | n/d | n/d | 0.0 |
| 1998 | 1,783.3 | 1,783.3 | n/d | n/d | 0.0 |
| 1999 | 1,580.1 | 1,580.1 | n/d | n/d | 0.0 |
| 2000 | 1,461.7 | 1,461.7 | n/d | n/d | 0.0 |
| 2001 | 1,300.1 | 1,300.1 | n/d | n/d | 0.0 |
| 2002 | 1,322.5 | 1,322.5 | n/d | n/d | 0.0 |
| 2003 | 1,806.7 | 1,806.7 | n/d | n/d | 0.0 |
| 2004 | 1,693.9 | 1,693.9 | n/d | n/d | 0.0 |
| 2005 | 1,938.6 | 1,938.6 | n/d | n/d | 0.0 |
| 2006 | 1,569.4 | 1,569.4 | n/d | n/d | 0.0 |
| 2007 | 1,509.6 | 1,509.6 | n/d | n/d | 0.0 |
| 2008 | 2,103.3 | 2,103.3 | n/d | n/d | 0.0 |
| 2009 | 2,283.3 | 2,283.3 | n/d | n/d | 0.0 |
| 2010 | 1,647.8 | 1,647.8 | n/d | n/d | 0.0 |
| 2011 | 1,496.1 | 1,496.1 | n/d | n/d | 0.0 |
| 2012 | 1,365.3 | 1,365.3 | n/d | n/d | 0.0 |
| 2013 | 1,882.2 | 1,882.2 | n/d | n/d | 0.0 |
| 2014 | 1,097.7 | 1,097.7 | n/d | n/d | 0.0 |
| 2015 | 1,450.5 | 1,450.5 | n/d | n/d | 0.0 |
| 2016 | 1,507.1 | 1,507.1 | n/d | n/d | 0.0 |
| 2017 | 912.6 | 1,324.9 | 912.6 | n/d | -412.3 |
| 2018 | 1,136.3 | 1,645.6 | 1,136.3 | n/d | -509.3 |
| 2019 | 1,143.3 | 1,456.9 | 1,143.3 | n/d | -313.6 |
| 2020 | 1,366.4 | 1,732.9 | 1,366.4 | n/d | -366.5 |
| 2021 | 997.4 | 1,663.3 | 997.4 | n/d | -665.9 |
| 2022 | 1,339.7 | 1,713.4 | 1,339.7 | n/d | -373.7 |
| 2023 | 989.6 | 1,557.0 | 989.6 | n/d | -567.4 |
| 2024 | 1,089.8 | 1,536.7 | 1,089.8 | n/d | -446.9 |
| 2025 | 624.3 | 1,018.2 | 624.3 | n/d | -393.9 |

## 2. Médias por período (mm/ano)

| Modelo | 1995–2009 | 2010–2025 | variação | 1995–2016 | 2017–2025 | variação |
|---|---|---|---|---|---|---|
| best_match | 1,731 | 1,253 | -28% | 1,655 | 1,067 | -36% |
| era5 | 1,731 | 1,506 | -13% | 1,655 | 1,517 | -8% |
| era5_land | n/d | n/d | n/d | n/d | n/d | n/d |
| ecmwf_ifs | n/d | 1,067 | n/d | n/d | 1,067 | n/d |

Nota: ecmwf_ifs só tem dados a partir de 2017-01-01 e era5_land retornou 100% null para esta célula (e para dois pontos vizinhos testados), então ambos não têm comparação de períodos longos.

## 3. Dias com chuva >= 1 mm por ano

| Ano | best_match | era5 | ecmwf_ifs |
|---|---|---|---|
| 1995 | 174 | 174 | n/d |
| 1996 | 203 | 203 | n/d |
| 1997 | 168 | 168 | n/d |
| 1998 | 188 | 188 | n/d |
| 1999 | 182 | 182 | n/d |
| 2000 | 151 | 151 | n/d |
| 2001 | 163 | 163 | n/d |
| 2002 | 157 | 157 | n/d |
| 2003 | 168 | 168 | n/d |
| 2004 | 188 | 188 | n/d |
| 2005 | 177 | 177 | n/d |
| 2006 | 182 | 182 | n/d |
| 2007 | 153 | 153 | n/d |
| 2008 | 201 | 201 | n/d |
| 2009 | 201 | 201 | n/d |
| 2010 | 168 | 168 | n/d |
| 2011 | 165 | 165 | n/d |
| 2012 | 155 | 155 | n/d |
| 2013 | 182 | 182 | n/d |
| 2014 | 132 | 132 | n/d |
| 2015 | 177 | 177 | n/d |
| 2016 | 155 | 155 | n/d |
| 2017 | 137 | 150 | 137 |
| 2018 | 148 | 191 | 148 |
| 2019 | 147 | 166 | 147 |
| 2020 | 146 | 158 | 146 |
| 2021 | 142 | 164 | 142 |
| 2022 | 163 | 176 | 163 |
| 2023 | 137 | 163 | 137 |
| 2024 | 125 | 159 | 125 |
| 2025 | 110 | 154 | 110 |
| média 1995–2009 | 177.1 | 177.1 | n/d |
| média 2010–2016 | 162.0 | 162.0 | n/d |
| média 2017–2025 | 139.4 | 164.6 | 139.4 |

## 4. Onde best_match muda de regime

| Ano | dias | dias bm == era5 | dias bm == ifs | dias bm != era5 |
|---|---|---|---|---|
| 1995 | 365 | 365 | 0 | 0 |
| 1996 | 366 | 366 | 0 | 0 |
| 1997 | 365 | 365 | 0 | 0 |
| 1998 | 365 | 365 | 0 | 0 |
| 1999 | 365 | 365 | 0 | 0 |
| 2000 | 366 | 366 | 0 | 0 |
| 2001 | 365 | 365 | 0 | 0 |
| 2002 | 365 | 365 | 0 | 0 |
| 2003 | 365 | 365 | 0 | 0 |
| 2004 | 366 | 366 | 0 | 0 |
| 2005 | 365 | 365 | 0 | 0 |
| 2006 | 365 | 365 | 0 | 0 |
| 2007 | 365 | 365 | 0 | 0 |
| 2008 | 366 | 366 | 0 | 0 |
| 2009 | 365 | 365 | 0 | 0 |
| 2010 | 365 | 365 | 0 | 0 |
| 2011 | 365 | 365 | 0 | 0 |
| 2012 | 366 | 366 | 0 | 0 |
| 2013 | 365 | 365 | 0 | 0 |
| 2014 | 365 | 365 | 0 | 0 |
| 2015 | 365 | 365 | 0 | 0 |
| 2016 | 366 | 366 | 0 | 0 |
| 2017 | 365 | 133 | 365 | 232 |
| 2018 | 365 | 106 | 365 | 259 |
| 2019 | 365 | 119 | 365 | 246 |
| 2020 | 366 | 117 | 366 | 249 |
| 2021 | 365 | 123 | 365 | 242 |
| 2022 | 365 | 112 | 365 | 253 |
| 2023 | 365 | 112 | 365 | 253 |
| 2024 | 366 | 144 | 366 | 222 |
| 2025 | 365 | 127 | 365 | 238 |

Primeiro dia em que best_match != era5: **2017-01-01**; ecmwf_ifs tem o primeiro valor em 2017-01-01. De 1995-01-01 a 2016-12-31 best_match == era5 em todos os dias; de 2017-01-01 a 2026-11-11 best_match == ecmwf_ifs em todos os dias.

Razão ecmwf_ifs / era5 (totais anuais) em 2017–2025:

| Ano | ifs/era5 | dias>=1mm ifs | dias>=1mm era5 |
|---|---|---|---|
| 2017 | 0.69 | 137 | 150 |
| 2018 | 0.69 | 148 | 191 |
| 2019 | 0.78 | 147 | 166 |
| 2020 | 0.79 | 146 | 158 |
| 2021 | 0.60 | 142 | 164 |
| 2022 | 0.78 | 163 | 176 |
| 2023 | 0.64 | 137 | 163 |
| 2024 | 0.71 | 125 | 159 |
| 2025 | 0.61 | 110 | 154 |

Razão média 2017–2025: 0.70 (soma ifs / soma era5 = 0.70).

## 5. Comparação com observações independentes

Observações: Galeão (NOAA GHCN) 2020 = 930,5 mm/96 dias >=1 mm; 2021 = 765,4 mm/79 dias. Alerta Rio (média da rede) 1997–2024 = 1.238,4 mm/ano; 2024 = 1.198,2 mm; 2025 = 890,9 mm (lidos por resumo automático, aproximados). Galeão é ponto único (~-22,81; -43,25), a rede Alerta Rio é média espacial de estações; nenhum é a célula exata dos modelos.

| Métrica | Obs | best_match | era5 | ecmwf_ifs |
|---|---|---|---|---|
| Total 2020 (mm) | 930,5 | 1,366.4 | 1,732.9 | 1,366.4 |
| Total 2021 (mm) | 765,4 | 997.4 | 1,663.3 | 997.4 |
| Dias>=1mm 2020 | 96 | 146 | 158 | 146 |
| Dias>=1mm 2021 | 79 | 142 | 164 | 142 |
| Total 2024 (mm) | 1.198,2 (Alerta Rio) | 1,089.8 | 1,536.7 | 1,089.8 |
| Total 2025 (mm) | 890,9 (Alerta Rio) | 624.3 | 1,018.2 | 624.3 |
| Média 1997–2024 (mm/ano) | 1.238,4 (Alerta Rio) | 1,476.2 | 1,606.7 | n/d (só 2017+) |

Viés relativo (modelo/obs - 1):

| Comparação | best_match | era5 | ecmwf_ifs |
|---|---|---|---|
| Galeão 2020 | +47% | +86% | +47% |
| Galeão 2021 | +30% | +117% | +30% |
| Alerta Rio 2024 | -9% | +28% | -9% |
| Alerta Rio 2025 | -30% | +14% | -30% |
| Alerta Rio média 1997–2024 | +19% | +30% | n/d |

Dias >= 1 mm vs Galeão: 2020 obs 96 -> bm/ifs 146, era5 158; 2021 obs 79 -> bm/ifs 142, era5 164.

## 6. A queda de patamar no modelo homogêneo (era5)

| Estatística (era5, totais anuais) | Valor |
|---|---|
| Média 1995–2009 | 1,731 mm (dp 298) |
| Média 2010–2025 | 1,506 mm (dp 226) |
| Diferença | -225 mm (-13%); p de permutação (20.000, bilateral) = 0.024 |
| Tendência linear 1995–2025 | -10.2 mm/ano; p de permutação = 0.072 |
| Tendência linear 1995–2016 (período em que bm == era5) | -11.6 mm/ano; p de permutação = 0.262 |
| era5 média 1995–2016 vs 2017–2025 | 1,655 vs 1,517 mm (-8%) |
| best_match média 1995–2016 vs 2017–2025 | 1,655 vs 1,067 mm (-36%) |
| era5 média 2010–2016 | 1,492 mm (vs 1,731 em 1995–2009: -14%) |
| Alerta Rio 1997–2024 (obs) vs era5 1997–2024 | 1.238 vs 1,607 mm |

## 7. Leitura e recomendação

**Documentação** (https://open-meteo.com/en/docs/historical-weather-api, lida via WebFetch, que devolve um resumo e não o texto bruto): lista ECMWF IFS (9 km, 2017–presente), ERA5 (~25 km, 1940–presente), ERA5-Land (~11 km, 1950–presente) e diz que o Best Match "combina IFS HRES, ERA5 e ERA5-Land" e que, para dados consistentes por várias décadas, se deve selecionar "ERA5" ou "ERA5-Land". O resumo não trouxe os identificadores de API; `best_match`, `era5`, `era5_land` e `ecmwf_ifs` foram aceitos pela API na prática.

**Evidência nos dados:**
- best_match é idêntico a era5 em todos os 8.036 dias de 1995-01-01 a 2016-12-31 e idêntico a ecmwf_ifs em todos os 3.602 dias de 2017-01-01 a 2026-11-11. A emenda é exatamente em 2017-01-01, mesmo ano de início do IFS na tabela da documentação.
- No ponto pedido, o IFS dá em média 0,70 do total anual do ERA5 em 2017–2025 (faixa 0,60–0,79) e menos dias >= 1 mm (139 vs 165 por ano). A queda de patamar do best_match em 2017 é, portanto, em grande parte troca de produto.
- Não há traço de ERA5-Land no best_match neste ponto; o próprio era5_land veio todo null aqui, então esse ramo da hipótese não pôde ser testado.

**Qual modelo é mais consistente / mais próximo das observações:**
- Consistência temporal: era5 (produto único em todo o período). best_match mistura dois produtos; ecmwf_ifs só existe a partir de 2017.
- Proximidade das observações: não há vencedor limpo. O IFS (= best_match 2017+) fica mais perto do Galeão (+30% a +47% vs +86% a +117% do ERA5) e do Alerta Rio 2024 (-9% vs +28%), mas fica mais longe em 2025 (-30% vs +14%). Em dias >= 1 mm todos superestimam (Galeão: 96 e 79 observados; IFS 146 e 142; ERA5 158 e 164), com o ERA5 pior. O ERA5 supera o Alerta Rio em +30% na média 1997–2024 (1.607 vs 1.238 mm). Observações de Galeão são ponto único e as do Alerta Rio vieram de resumo automático: comparação indicativa.

**Recomendação para a série principal: era5.** É o único candidato homogêneo em 1995–2025 e a documentação indica ERA5/ERA5-Land para consistência multidecadal. Ele tem viés úmido (~+30% vs Alerta Rio), então serve para anomalias e tendência relativas, não para volumes absolutos. O best_match não deve ser usado para comparar períodos que cruzam 2017.

**A queda 2010+ sobrevive?** Parcialmente. No era5, 1995–2009 = 1.731 mm e 2010–2025 = 1.506 mm (-13%, p de permutação 0,024), contra -28% no best_match: cerca de metade da queda aparente é artefato da emenda de 2017. A queda residual existe nos totais do ERA5, mas a tendência linear 1995–2025 não é significativa a 5% (p 0,072) e a de 1995–2016 também não (p 0,26); uma única célula de ~25 km e a grande variabilidade interanual (dp ~260 mm) limitam a conclusão. Veredito: queda de -28% é majoritariamente artefato; a queda de -13% no ERA5 é sugestiva, mas inconclusiva como mudança de regime.
