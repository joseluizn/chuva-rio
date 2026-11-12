# Revisão — chuva_rio.html (versão longa)

Critério: skill `datavis` do usuário (Tufte data-ink, Okabe-Ito/viridis, título = achado, incerteza explícita, eixo único) + skill `dataviz` (um eixo; sequencial uma matiz; legenda/rótulos; tema escuro validado; renderizar e olhar). Literatura citada pelo nome; opinião marcada como tal.

## Verificações numéricas (python3 -I contra rain_rio.json)
- Lead: 227,4/46,3 = 4,91× ✓; 18,7/8,0 = 2,34× ✓; 12,0/5,6 = 2,14× ✓; soma dias chuvosos 163,4 ✓; média anual 1.484,4 (31 anos completos) ✓; extremos 3/jan 81% e 1/ago 3% ✓.
- Junho (46,3) e julho (46,8) empatam como "mais seco"; a frase trata como fato uma diferença de 0,5 mm.
- "31 anos por célula" (make_page.py l.539): errado — by_day tem n_years 32 até 11/nov, 31 depois, 8 em 29/fev.
- Totais anuais ERA5: média 1995–2009 = 1.731 mm; 2010–2025 = 1.253 mm (−28%); 2025 = 624 mm (2025: fev 4,7 mm, mai 18,8 mm). A série NÃO é estacionária (ou tem quebra de homogeneidade). A página nunca mostra a série anual; a "média" de 1.484 mistura dois regimes. Curiosamente, a média 2010–2025 (1.253) bate com Alerta Rio (1.238), o que torna a frase "ERA5 superestima ~20%" dependente do período.
- Variância dia-a-dia de p_wet dentro de cada mês ÷ variância binomial esperada com n≈32: 1,29. Ou seja, ~77% da variação entre dias vizinhos no mapa de calor é ruído amostral puro.
- Participação mensal (% do total anual): ERA5 vs Alerta Rio vs INMET fica a ±2–3 p.p.; % de dias chuvosos ERA5 vs INMET, ±1–3 p.p. Em escala relativa o viés quase some.
- Contraste: rampa clara #cde2fb sobre a superfície = 1,29:1; #cde2fb vs cor de "sem dia chuvoso" (#e1e0d9) = 1,0:1 (indistinguíveis); no escuro #0d366b sobre #1a1a19 = 1,46:1. --muted 3,5:1 (só passa para texto grande).
- Nenhum dia tem p_wet = 0 ou mediana nula → a legenda "sem dia chuvoso" descreve algo que não existe.
- Checagem com o Galeão (2020/2021) não aparece em lugar nenhum da página (grep "gale" = 0).

## Parte 1 — problemas
### Bloqueantes
1. **Não-estacionariedade escondida.** Evidência acima. Princípio: datavis §8 (respeitar a incerteza); Wilke cap. 13 (séries temporais devem ser mostradas antes de agregados). Correção: painel de totais anuais (linha + pontos, 1995–2025, 2026 vazado/parcial, refs como linhas horizontais), e mencionar no lead que a média depende do período; oferecer ao menos 1995–2009 vs 2010–2025.
2. **Viés do ERA5 só na nota.** O lead afirma "227 mm em média" como fato do Rio. Princípio: datavis §7 (anotar onde o leitor decide). Correção: subtítulo no lead "Reanálise ERA5 (célula de grade), que superestima volume (~20%) e sobretudo frequência (~75%) frente a pluviômetros"; no painel de dias chuvosos, rótulo direto "INMET: 93 dias/ano vs ERA5: 163"; citar Galeão 2020/21.
3. **"Fonte dos dados" vazio** — bug: `.ctl{display:flex}` sobrepõe o atributo `hidden` (l.89 vs l.151/304). Correção: `[hidden]{display:none!important}`.

### Importantes
4. **Volume×frequência não comparáveis.** Três escalas distintas; a pergunta é sobre co-variação. Cleveland & McGill: posição em escala comum é a codificação mais precisa; skill dataviz: "dois medidas de escala diferente → indexar a base comum". Correção: painel principal = % do total anual e % dos dias chuvosos anuais por mês, em um eixo (duas linhas/pontos, Okabe-Ito + rótulo direto). Isso também neutraliza o viés absoluto (participações batem com refs). Alternativa: dispersão conectada dias×mm/mês (12 pontos em ciclo) — opinião: mais bonita, menos legível para leigos; usar como secundário.
5. **Barra de média + whisker p10–p90 ("dynamite plot").** Weissgerber et al. 2015 (PLoS Biol); Wilke cap. 9. Barra codifica média, whisker codifica quantis de outra estatística; o strip da seção 3 já mostra a distribuição. Correção: substituir por ponto na mediana + faixa p10–p90 (ou remover a faixa e remeter ao strip).
6. **Mapa de calor sugere estrutura que é ruído** (razão 1,29). Correção: suavização ligada por padrão (ou ajuste harmônico de 2–3 termos), dado bruto como opção; adicionar um gráfico de linha do ciclo anual (366 dias, p_wet suavizada com banda binomial ~±9 p.p.); responder "distribuição ao longo do mês" com perfil por decêndio (1–10/11–20/21–fim) e IC — resposta provável: não há padrão intra-mês além do gradiente sazonal, e a página deveria dizer isso. Agregar por pêntadas é razoável; meses quebrados não têm sentido físico (opinião informada: o calendário civil é arbitrário para clima).
7. **Escala de cor**: uma matiz azul, interpolação RGB (não perceptual), extremo baixo quase invisível (1,29:1). Skill datavis §2 recomenda viridis/cividis; WCAG 1.4.11 (3:1 para objetos gráficos). Correção: rampa perceptual (cividis ou blues em OKLab) com extremo claro ≥ ~1,5:1 e remover item "sem dia chuvoso". Domínio p_wet 0–100% desperdiça o topo (máx 81%) — usar 0–90%.
8. **Inglês vazando**: meta l.296 repete "(Open-Meteo ... grid-cell, not a gauge)"; 5 "Nota da fonte" em inglês (l.643). Traduzir ou remover; notas técnicas viram uma linha em português.
9. **Textos desatualizados/frágeis**: "31 anos por célula"; "junho o mais seco" (empate); `|| true` no focus (l.406).
10. **Sobreposição**: "mm no mês" colide com o rótulo 600 do eixo (desk e dark); título do painel colado ao tick 400. Correção: título acima da área do gráfico com margem ≥ 14 px.

### Menores
11. Referências: losango/círculo deslocados lateralmente e encostados no whisker — difícil ler; no mobile se sobrepõem. Usar tique horizontal fino em vez de marcador, ou mover para o gráfico relativo.
12. Mobile (390 px): legenda do overview em 4 linhas, mapa de calor com células ~10 px, nota com URL longa. Recolher a nota metodológica em `<details>`.
13. Rótulos de extremos (227/46, 19,5/7,4, 12,0/5,6) — bom por datavis §7, mas títulos dos painéis descrevem métrica, não achado.
14. Teclado: existe navegação por setas e tooltip em aria-live — bom; mapa de calor com `role=grid` sem células `gridcell` é semântica incorreta (usar role=img + tabela).
15. Tema escuro: rampa invertida é decisão válida (dataviz: modo escuro "selecionado"), mas o extremo baixo some no fundo (1,46:1).

### Remover
- Item de legenda "sem dia chuvoso"; "Fonte dos dados"; as notas de fonte em inglês; a repetição da fonte na linha meta; whiskers p10–p90 sobre barras; a frase-correlação r = 0,97 (12 pontos com ciclo sazonal forte: r alto é trivial e não valida nada); o painel "Intensidade" como barra separada (vira derivado no tooltip ou no gráfico relativo/dispersão).

## Lista priorizada (ver relatório curto)

## Parte 2 — Dashboard
Ver relatório curto; nada a acrescentar além de: pré-processar no build (Python) os agregados por janela e enviar também a série diária compacta (inteiros em décimos de mm, ~11.6k valores ≈ 40–60 KB) para recomputo de limiar/período; bootstrap por bloco de ano (não por dia) para preservar autocorrelação.
