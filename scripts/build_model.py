#!/usr/bin/env python3
"""Gera site/modelo.html (página do modelo por decêndio, abril a outubro).

Lê data/derived/periodos_abr_out.json (gerado por scripts/model_periods.py) e
scripts/model_template.html. Só biblioteca padrão; idempotente (sem relógio).

Uso: python3 scripts/build_model.py
"""
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "data", "derived", "periodos_abr_out.json")
TPL = os.path.join(HERE, "model_template.html")
OUT = os.path.join(ROOT, "site", "modelo.html")
REPO = "https://github.com/joseluizn/chuva-rio"
DOC = REPO + "/blob/main/docs/modelo_periodos.md"
NCEI_URL = "https://www.ncei.noaa.gov/products/land-based-station/comparative-climatic-data"
ATTR_HTML = ('Dados: <a href="https://open-meteo.com/">Open-Meteo.com</a> '
             '(<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>), '
             'reanálise ERA5 — <a href="https://cds.climate.copernicus.eu/">Copernicus/ECMWF</a>.')
MN = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

# (chave no JSON, nome no controle, nome longo, substantivo, inverter?, regras de "período bom")
# A página fala sempre em TEMPO BOM: para chuva mostra a fração de dias SEM chuva
# (1 − p), de modo que "mais alto = melhor" vale para todos os desfechos.
OUTCOMES = [
    ("bom", "Dia bom", "dia bom (céu aberto e sem chuva)", "dias bons", False,
     ["5 ou mais dias bons", "7 ou mais dias bons"]),
    ("open", "Céu aberto", "céu aberto", "dias de céu aberto", False,
     ["5 ou mais dias de céu aberto", "7 ou mais dias de céu aberto"]),
    ("rain", "Sem chuva", "dia sem chuva (menos de 1 mm)", "dias sem chuva", True,
     ["no máximo 2 dias com chuva", "nenhum dia com chuva"]),
    ("rain_ge5mm", "Sem chuva forte", "dia sem chuva forte (menos de 5 mm)", "dias sem chuva forte", True,
     ["no máximo 1 dia com chuva forte", "nenhum dia com chuva forte"]),
]
MESES = {"abr": "abril", "mai": "maio", "jun": "junho", "jul": "julho", "ago": "agosto", "set": "setembro",
         "out": "outubro"}
# Escala de probabilidade do IPCC AR5 (Mastrandrea et al. 2010), termo mais específico.
TERMS = [(0.99, "praticamente certo"), (0.90, "muito provável"), (0.66, "provável"),
         (0.33, "tão provável quanto improvável"), (0.10, "improvável"), (0.01, "muito improvável"),
         (0.0, "excepcionalmente improvável")]


def term(p):
    for t, n in TERMS:
        if p >= t - 1e-9:
            return n
    return TERMS[-1][1]


def pshow(p):
    if p >= 0.995:
        return "mais de 99%"
    if p < 0.005:
        return "menos de 1%"
    r = round(100 * p) / 100
    if any(p < t - 1e-9 and r >= t for t in (0.99, 0.90, 0.66, 0.33, 0.10, 0.01)):
        return pct(p, 1)
    return pct(p)


# ------------------------------------------------------------------ formatação
def fmt(x, d=0):
    s = f"{x:,.{d}f}"
    return s.replace(",", "\u0000").replace(".", ",").replace("\u0000", ".")


def pct(x, d=0):
    return fmt(100 * x, d) + "%"


def fdate(iso):
    y, m, d = (int(v) for v in iso.split("-"))
    return f"{d}/{MN[m - 1]}/{y}"


# ------------------------------------------------------------- cores (OKLCH)
def _oklch_to_srgb(L, c, h):
    a, b = c * math.cos(math.radians(h)), c * math.sin(math.radians(h))
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    rgb = [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
           -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
           -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s]
    out = []
    for v in rgb:
        v = min(1, max(0, v))
        out.append(12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055)
    return out


def _hex(rgb):
    return "#" + "".join(f"{round(v * 255):02x}" for v in rgb)


def seq_ramp(hue, n=9):
    """Uma matiz, claro -> escuro nos dois temas (convenção do site: mais escuro = mais)."""
    light = [_oklch_to_srgb(0.96 - (0.96 - 0.33) * i / (n - 1), 0.025 + 0.11 * math.sin(math.pi * i / (n - 1) * 0.8), hue)
             for i in range(n)]
    dark = [_oklch_to_srgb(0.92 + (0.40 - 0.92) * i / (n - 1), 0.04 + 0.11 * (i / (n - 1)), hue) for i in range(n)]
    return {"light": [_hex(c) for c in light], "dark": [_hex(c) for c in dark]}


# ------------------------------------------------------------------ textos
def runs(idx_list, labels):
    """Índices -> texto com trechos contíguos ('jun 11–20 a set 1–10 e out 1–10')."""
    idx = sorted(idx_list)
    if not idx:
        return ""
    groups, cur = [], [idx[0]]
    for i in idx[1:]:
        if i == cur[-1] + 1:
            cur.append(i)
        else:
            groups.append(cur)
            cur = [i]
    groups.append(cur)
    parts = [labels[g[0]] if len(g) == 1 else f"{labels[g[0]]} a {labels[g[-1]]}" for g in groups]
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " e " + parts[-1]


def friendly(label):
    """'jul 1–10' -> 'início de julho'."""
    m, d = label.split(" ")
    pos = {"1": "início", "11": "meados", "21": "fim"}[d.split("–")[0]]
    return f"{pos} de {MESES[m]}"


def run_friendly(la, lb):
    """'do início de junho ao fim de agosto'."""
    def part(label, to):
        m, d = label.split(" ")
        k = d.split("–")[0]
        if to:
            w = {"1": "ao início", "11": "a meados", "21": "ao fim"}[k]
        else:
            w = {"1": "do início", "11": "de meados", "21": "do fim"}[k]
        return f"{w} de {MESES[m]}"
    if la == lb:
        return friendly(la)
    return f"{part(la, False)} {part(lb, True)}"


def flip_ci(ci):
    return [round(1 - ci[1], 4), round(1 - ci[0], 4)]


def page_outcome(o, inv, rules, dg):
    """Arrays da página para um desfecho; para chuva, inverte para 'sem chuva'."""
    dec = o["decendios"]
    pw = o["pairwise"]
    py = o["per_year"]
    f = (lambda v: round(1 - v, 4)) if inv else (lambda v: v)
    fc = flip_ci if inv else (lambda c: c)
    neg = (lambda v: -v) if inv else (lambda v: v)
    r4 = lambda v: None if v is None else round(v, 4)
    cal = dg["calibration"]
    return {
        "nd": [x["n_days_window"] for x in dec],
        "pm": [f(x["p_model"]) for x in dec],
        "pml": [fc(x["p_model_boot90"])[0] for x in dec], "pmh": [fc(x["p_model_boot90"])[1] for x in dec],
        "pr": [f(x["p_raw"]) for x in dec],
        "prl": [fc(x["p_raw_boot90"])[0] for x in dec], "prh": [fc(x["p_raw_boot90"])[1] for x in dec],
        "pb": [x["P_best"] for x in dec], "pbr": [x["P_best_raw"] for x in dec],
        "pt3": [x["P_top3"] for x in dec], "pt3r": [x["P_top3_raw"] for x in dec],
        "tier": [x["tier"] for x in dec], "amb": [1 if x["tier_ambiguous"] else 0 for x in dec],
        "rdm": [x["rank_dist_model"] for x in dec], "rdr": [x["rank_dist_raw"] for x in dec],
        "rmm": [x["rank_median_model"] for x in dec], "rcm": [x["rank_ci90_model"] for x in dec],
        "rmr": [x["rank_median_raw"] for x in dec], "rcr": [x["rank_ci90_raw"] for x in dec],
        # P(linha melhor que coluna): "melhor" já é "menos chuva" no JSON, igual a "mais dias sem chuva".
        "pwr": pw["P_better_raw"], "pwm": pw["P_better_model"],
        "dif": [[neg(v) for v in row] for row in pw["diff_raw"]],
        "dci": [[([-c[1], -c[0]] if inv else c) for c in row] for row in pw["diff_raw_ci90"]],
        "exz": [[1 if v else 0 for v in row] for row in pw["ci_excludes_zero"]],
        "py": {"years": py["years"], "partial": py["partial_year"],
               "count": [[(n - c if inv else c) for c, n in zip(cr, nr)] for cr, nr in zip(py["count"], py["n"])],
               "n": py["n"],
               "good": [{"label": lab, "share": g["share_years"], "ci": g["wilson90"]}
                        for lab, g in zip(rules, py["good"])]},
        "cal": {"pin": [f(v) for v in cal["pred_in_sample"]],
                "ploo": [f(v) for v in cal["pred_loyo"]] if cal["pred_loyo"] else None,
                "obs": [f(v) for v in cal["obs"]], "oci": [fc(c) for c in cal["obs_boot90"]]},
    }


def k_table_html(key, short, dg, K):
    sel = ' class="sel"'
    rows = "".join(
        f"<tr{sel if r['K'] == K else ''}><td>{r['K']}{' ✓' if r['K'] == K else ''}</td><td>{r['n_params']}</td>"
        f"<td>{fmt(r['cv_logloss'], 4)} ± {fmt(r['cv_logloss_se'], 4)}</td>"
        f"<td>{fmt(r['cv_diff_vs_min'], 4)} ± {fmt(r['cv_diff_se'], 4)}</td>"
        f"<td>{fmt(r['aic'])}</td><td>{fmt(r['bic'])}</td></tr>" for r in dg["k_table"])
    return (f'<div class="tw" data-out="{key}"><table><caption>{short}: K = {K} escolhido (mínimo da validação cruzada em '
            f'K = {dg["K_min_cv"]}; AIC prefere K = {dg["K_min_aic"]}; BIC, K = {dg["K_min_bic"]}). Proporções brutas por '
            f'decêndio como previsão para um ano novo: log-loss {fmt(dg["raw_decendio_cv_logloss"], 4)}.</caption>'
            f'<thead><tr><th>K</th><th>Parâm.</th><th>Log-loss CV (± EP entre anos)</th><th>Dif. p/ o mínimo (± EP)</th>'
            f'<th>AIC</th><th>BIC</th></tr></thead><tbody>{rows}</tbody></table></div>')


def main():
    if not os.path.exists(SRC):
        sys.exit("ERRO: data/derived/periodos_abr_out.json não existe; rode scripts/model_periods.py antes.")
    J = json.load(open(SRC, encoding="utf-8"))
    meta = J["meta"]
    labels = meta["decendio_labels"]
    keys = meta["decendio_keys"]
    avail = [o for o in OUTCOMES if o[0] in J["outcomes"]]
    nb = meta["model"]["n_boot"]
    y0, y1 = meta["years_used_rain"]
    ny = meta["n_years_rain"]
    partial = meta.get("partial_year_excluded")
    data = {"keys": keys, "labels": labels, "friendly": [friendly(l) for l in labels], "o": {},
            "order": [o[0] for o in avail], "ramp": seq_ramp(165.0),
            "nBoot": nb, "years": meta["years_used_rain"], "partial": partial,
            "terms": [[t, n] for t, n in TERMS]}
    ktabs = []
    for key, short, name, noun, inv, rules in avail:
        o = J["outcomes"][key]
        dg = meta["diagnostics"][key]
        d = page_outcome(o, inv, rules, dg)
        noun1 = {"dias bons": "dia bom", "dias de céu aberto": "dia de céu aberto", "dias sem chuva": "dia sem chuva",
                 "dias sem chuva forte": "dia sem chuva forte"}[noun]
        d.update({"short": short, "name": name, "noun": noun, "noun1": noun1, "K": o["K"],
                  "ib": keys.index(o["best_point"]), "iw": keys.index(o["worst_point"]),
                  "ibr": keys.index(o["best_modal_raw"])})
        data["o"][key] = d
        ktabs.append(k_table_html(key, short, dg, o["K"]))

    # ---- título: desfecho padrão (o primeiro), com escala de probabilidade
    k0, short0, name0, noun0 = avail[0][:4]
    o0 = J["outcomes"][k0]
    dec0 = o0["decendios"]
    ib0 = keys.index(o0["best_point"])
    t1 = sorted(j for j, x in enumerate(dec0) if x["tier"] == 1)
    p_run = sum(dec0[j]["P_best_raw"] for j in t1)
    if t1[-1] - t1[0] == len(t1) - 1:
        where = f"vai {run_friendly(labels[t1[0]], labels[t1[-1]])}"
    else:
        where = f"está em {runs(t1, labels)}"
    pm0 = data["o"][k0]["pm"][ib0]
    nd0 = dec0[ib0]["n_days_window"]
    title = (f"{short0} entre abril e outubro: o melhor período {where} "
             f"({term(p_run)}, {pshow(p_run)}), mas dentro dessa faixa nenhum período se destaca claramente; "
             f"no pico, {friendly(labels[ib0])}, são cerca de {fmt(pm0 * nd0)} {noun0 if round(pm0 * nd0) != 1 else data['o'][k0]['noun1']} em {nd0}")
    lead = (f"Cada mês de abril a outubro foi dividido em três períodos (os decêndios): dias 1–10 (início), 11–20 "
            f"(meados) e 21 ao fim (fim do mês). A página compara os 21 períodos para quatro definições de tempo bom: "
            f"dia bom (céu aberto e sem chuva), céu aberto, sem chuva e sem chuva forte. Em todos os gráficos, mais alto "
            f"é melhor. Base: {ny} anos completos de reanálise ERA5 ({y0}–{y1})"
            f"{f'; {partial} ainda está incompleto e fica de fora' if partial else ''}.")
    unc = (f"<b>Como medimos a incerteza.</b> Refizemos a conta {fmt(nb)} vezes, cada vez com um conjunto de {ny} anos "
           f"sorteados (com repetição) entre {y0} e {y1}, como se tivéssemos {fmt(nb)} históricos alternativos. Quando "
           f"dizemos que um período é o melhor em 70% das simulações, é em {fmt(round(0.7 * nb))} desses {fmt(nb)} históricos "
           f"simulados. A <b>faixa de 90%</b> é o intervalo onde caem 90% dos históricos simulados. As chances viram "
           f"palavras numa escala fixa: praticamente certo (99% ou mais), muito provável (90% ou mais), provável (66% ou "
           f"mais), tão provável quanto improvável (33% a 66%), improvável (menos de 33%), muito improvável (menos de "
           f"10%) e excepcionalmente improvável (menos de 1%). Elas medem só a variação entre anos, não os erros da reanálise.")
    caveat = ("<b>Leia antes do ranking.</b> No meio do ano, a diferença entre períodos vizinhos é menor que a diferença "
              "entre um ano e outro; por isso os gráficos mostram faixas e chances, não só o vencedor. A reanálise ERA5 "
              "inventa muitos dias de chuva fraca: na realidade, dias sem chuva são mais comuns do que aparece aqui. "
              "Use os números para comparar períodos, não como previsão para um ano específico.")

    # ---- robustez (tabela, sem jargão no corpo)
    rows = meta["diagnostics"]["robustness_rows"]
    lab = dict(zip(keys, labels))
    grp = {"split": "Metades da série", "threshold": "Outro limiar", "K": "Curva mais flexível",
           "cloud24h": "Nuvem nas 24 h", "sunshine": "Insolação", "obs": "Observação (Galeão)"}
    trs = []
    for r in rows:
        sp = "–" if r["spearman"] is None else fmt(r["spearman"], 2).replace("-", "−")
        sh = "" if r.get("share_days_apr_oct") is None else f" ({pct(r['share_days_apr_oct'])} dos dias)"
        trs.append(f"<tr><td>{grp.get(r['group'], r['group'])}</td><td>{r['label']}{sh}</td>"
                   f"<td>{', '.join(lab[k] for k in (r['top3'] or []))}</td><td>{sp}</td></tr>")
    rob_tbl = ("<table><caption>Os três melhores períodos em cada variação (para chuva, os de menos chuva) e a "
               "concordância de ordem dos 21 períodos com o resultado principal do mesmo desfecho (1 = mesma ordem, "
               "0 = nenhuma relação, −1 = ordem invertida).</caption>"
               "<thead><tr><th>Verificação</th><th>Variação</th><th>Três melhores</th><th>Concordância</th></tr></thead><tbody>"
               + "".join(trs) + "</tbody></table>")
    sun = [r for r in rows if r["group"] == "sunshine"]
    sun_txt = ""
    if sun:
        s06 = next((r for r in sun if "0,6" in r["label"]), sun[0])
        sq = sun[-1]
        sun_txt = (f"<b>Horas de sol não servem aqui.</b> A fração de horas de sol do ERA5 quase não acompanha a "
                   f"nebulosidade: com o corte de 0,6, {pct(s06['share_days_apr_oct'])} dos dias de abril a outubro "
                   f"seriam &ldquo;abertos&rdquo;, e a ordem dos períodos não tem relação com a da nebulosidade "
                   f"(concordância {fmt(s06['spearman'], 2).replace('-', '−')}); com um corte que dá a mesma fração de "
                   f"dias abertos, a ordem se inverte (concordância {fmt(sq['spearman'], 2).replace('-', '−')}). Por isso "
                   f"a página usa só a nebulosidade das 09 às 17 h.")
    gal = J["robustness"].get("ghcn_galeao_ge1mm")
    gal_txt = ""
    if gal:
        gp = [v for v in gal["p_raw"] if v is not None]
        gal_txt = (f"<b>Conferência com o Galeão.</b> A estação do aeroporto (NOAA) tem medições em só parte dos dias "
                   f"(de {min(gal['n_obs'])} a {max(gal['n_obs'])} por período). Lá, dias com chuva são bem mais raros "
                   f"(de {pct(min(gp))} a {pct(max(gp))} por período), coerente com o excesso de chuva fraca do ERA5, mas a "
                   f"forma da estação é parecida (concordância de ordem {fmt(gal['spearman_vs_era5_raw'], 2)}); os três "
                   f"períodos mais secos no Galeão são {', '.join(lab[k] for k in gal['top3'])}. Serve para conferir a forma, "
                   f"não o nível.")
    pers = meta["persistence_rain_ge1mm"]
    pers_txt = (f"<b>Por que sortear anos inteiros.</b> Dias de chuva vêm em sequência: de abril a outubro, depois de um "
                f"dia chuvoso a chance de chover de novo é {pct(pers['p_rain_after_rain'])}; depois de um dia seco, "
                f"{pct(pers['p_rain_after_dry'])}. Num mesmo período, as contagens variam de um ano para outro "
                f"{fmt(pers['variance_inflation_median'], 1)} vez mais do que variariam se os dias fossem independentes. "
                f"Sortear dias soltos subestimaria a incerteza.")
    thr = meta.get("open_threshold_pct")
    open_def = (f"Céu aberto = nebulosidade média das 09 às 17 h de até {fmt(thr)}% (classe &ldquo;clear&rdquo; do "
                f"<a href=\"{NCEI_URL}\">NOAA/NCEI</a>, 0 a 3/10 de céu coberto). Dia bom = céu aberto e chuva &lt; 1 mm."
                if thr is not None else "")
    source = (f"Fonte: Open-Meteo, reanálise ERA5, célula de grade de ~25 km (−22,75; −43,25); anos completos {y0}–{y1}, "
              f"dados até {fdate(meta['last_rain_date'])}. " + ATTR_HTML)

    tpl = open(TPL, encoding="utf-8").read()
    repl = {
        "TITLE": title, "LEAD": lead, "UNC": unc, "CAVEAT": caveat, "SOURCE": source, "ATTR": ATTR_HTML,
        "REPO": REPO, "DOC": DOC, "ROB_TBL": rob_tbl, "SUN_TXT": sun_txt, "GAL_TXT": gal_txt,
        "PERS_TXT": pers_txt, "OPEN_DEF": open_def, "NBOOT": fmt(nb), "NY": str(ny), "Y0": str(y0),
        "Y1": str(y1), "KTABS": "".join(ktabs),
        "OUT_RADIOS": "".join(
            f'<label><input type="radio" name="out" value="{k}"{" checked" if i == 0 else ""}><span>{s_}</span></label>'
            for i, (k, s_, *_rest) in enumerate(avail)),
        "DATA": json.dumps(data, ensure_ascii=False, separators=(",", ":")),
    }
    for k, v in repl.items():
        tpl = tpl.replace(f"%%{k}%%", v)
    left = re.findall(r"%%[A-Z0-9_]+%%", tpl)
    if left:
        sys.exit(f"marcadores sem valor: {sorted(set(left))}")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(tpl)
    os.replace(tmp, OUT)
    print(f"escrito {os.path.relpath(OUT, ROOT)} ({len(tpl.encode('utf-8')) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
