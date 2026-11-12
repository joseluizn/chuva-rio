# Chuva no Rio de Janeiro, 1995 até hoje

Visualização de 30 anos de chuva diária no Rio de Janeiro (ponto -22.9068, -43.1729), com a série da reanálise ERA5 via Open-Meteo, comparada a referências de estações (Alerta Rio, INMET, Galeão).

- Site: https://joseluizn.github.io/chuva-rio/
- Versão completa: https://joseluizn.github.io/chuva-rio/completo.html

## Achados principais

Os números mudam a cada atualização mensal; veja-os no site.

1. A chuva do Rio é fortemente sazonal: o verão concentra a maior parte do volume e o inverno é a estação seca.
2. A reanálise ERA5 superestima volume e, sobretudo, a frequência de dias chuvosos frente aos pluviômetros; as proporções por mês e a sazonalidade, porém, são bem preservadas.
3. A série anual não é estacionária, então a "média" depende do período escolhido (detalhes em `docs/analise_modelos.md` e `docs/revisao_opus.md`).

## Estrutura

```
data/daily/   era5.csv, ecmwf_ifs.csv, best_match.csv (date,precip_mm), era5_cloud.csv (nebulosidade) e meta.json
data/derived/ periodos_abr_out.json (modelo por decêndio, gerado por scripts/model_periods.py)
data/refs/    referências estáticas (Alerta Rio, INMET, Galeão/NOAA)
scripts/      fetch_data.py (coleta + validação), test_fetch_data.py, model_periods.py, build_main.py, build_full.py, common.py,
              main_template.html e full_template.html (modelos das duas páginas; os builds dependem deles)
site/         index.html e completo.html (publicados no GitHub Pages)
docs/         ATUALIZACAO.md, analise_modelos.md, modelo_periodos.md, revisao_opus.md
.github/workflows/   update-data.yml (mensal) e pages.yml (deploy)
```

## Rodar localmente

```bash
python3 -m unittest scripts/test_fetch_data.py   # testes do coletor, sem rede
python3 scripts/fetch_data.py                    # atualiza data/daily (precisa de internet)
python3 scripts/build_main.py && python3 scripts/build_full.py
open site/index.html                             # Linux: xdg-open
```

Passo a passo completo, falhas comuns e checklist: [docs/ATUALIZACAO.md](docs/ATUALIZACAO.md). A atualização dos dados roda sozinha todo dia 7 do mês (GitHub Actions).

## Dados, fontes e licença

- Dados meteorológicos: [Open-Meteo.com](https://open-meteo.com/) Historical Weather API, licença [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Reanálise ERA5: Copernicus Climate Change Service (C3S) / ECMWF. Nebulosidade e insolação: ERA5 via Open-Meteo, CC BY 4.0. As séries foram agregadas e processadas neste projeto; não há endosso da Open-Meteo. Uso da API gratuita restrito a fins não comerciais.
- Referências: Sistema Alerta Rio (relatórios anuais de chuva), INMET (normais climatológicas, via Wikipédia), NOAA NCEI GHCN-Daily (estação Galeão). Seguem as condições de cada fonte.
- Código: [MIT](LICENSE), Jose Luiz Nunes, 2026.

Documentação: [docs/ATUALIZACAO.md](docs/ATUALIZACAO.md) · [docs/analise_modelos.md](docs/analise_modelos.md) · [docs/modelo_periodos.md](docs/modelo_periodos.md) · [docs/revisao_opus.md](docs/revisao_opus.md)
