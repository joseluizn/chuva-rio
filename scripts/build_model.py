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

# (chave no JSON, nome no controle, nome longo, substantivo, cor CSS, rampa)
OUTCOMES = [
    ("rain", "Chuva ≥ 1 mm", "chuva (≥ 1 mm)", "dias chuvosos", "mm", "blue"),
    ("rain_ge5mm", "Chuva ≥ 5 mm", "chuva forte (≥ 5 mm)", "dias com ≥ 5 mm", "mm", "blue"),
    ("open", "Céu aberto", "céu aberto", "dias de céu aberto", "open", "green"),
    ("bom", "Dia bom", "dia bom (aberto e sem chuva)", "dias bons", "open", "green"),
]


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


def div_ramp(h_neg=55.0, h_pos=305.0, n=5):
    """Divergente laranja <-> roxo (PuOr) com meio cinza neutro; n passos por braço."""
    def arm(h, theme):
        out = []
        for i in range(1, n + 1):
            t = i / n
            if theme == "light":
                out.append(_oklch_to_srgb(0.95 - 0.47 * t, 0.17 * t ** 0.8, h))
            else:
                out.append(_oklch_to_srgb(0.32 + 0.42 * t, 0.15 * t ** 0.8, h))
        return out
    res = {}
    for theme, mid in (("light", _oklch_to_srgb(0.95, 0, 0)), ("dark", _oklch_to_srgb(0.32, 0, 0))):
        neg = list(reversed(arm(h_neg, theme)))
        pos = arm(h_pos, theme)
        res[theme] = [_hex(c) for c in neg + [mid] + pos]
    return res


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


def run_around(i, members):
    a = b = i
    while a - 1 in members:
        a -= 1
    while b + 1 in members:
        b += 1
    return a, b


def headline(o, name, noun, labels):
    dec = o["decendios"]
    ib, iw = [x["key"] for x in dec].index(o["best_point"]), [x["key"] for x in dec].index(o["worst_point"])
    ibr = [x["key"] for x in dec].index(o["best_modal_raw"])
    ext = "menos" if o["best_is"] == "lowest" else "mais"
    t1 = [j for j, x in enumerate(dec) if x["tier"] == 1]
    t3 = [j for j, x in enumerate(dec) if x["tier"] == 3]
    b = dec[ib]
    s = (f"<b>{name.capitalize()}.</b> O modelo suave põe o decêndio com {ext} {noun} em <b>{labels[ib]}</b>: "
         f"{pct(b['p_model'])} dos dias, ~{fmt(b['expected_days'], 1)} em {b['n_days_window']}. ")
    if ibr != ib:
        s += (f"Sem impor forma à curva, {labels[ib]} é o melhor em só {pct(b['P_best_raw'])} das réplicas; "
              f"o mais frequente é {labels[ibr]} ({pct(dec[ibr]['P_best_raw'])}). ")
    else:
        s += f"Sem impor forma à curva, ele é o melhor em {pct(b['P_best_raw'])} das réplicas. "
    s += (f"{len(t1)} dos 21 decêndios ({runs(t1, labels)}) não se distinguem do melhor; "
          f"no outro extremo, {len(t3)} ({runs(t3, labels)}) não se distinguem do pior, {labels[iw]} "
          f"({pct(dec[iw]['p_model'])}).")
    return s


def main():
    if not os.path.exists(SRC):
        sys.exit("ERRO: data/derived/periodos_abr_out.json não existe; rode scripts/model_periods.py antes.")
    J = json.load(open(SRC, encoding="utf-8"))
    meta = J["meta"]
    labels = meta["decendio_labels"]
    keys = meta["decendio_keys"]
    avail = [o for o in OUTCOMES if o[0] in J["outcomes"]]
    data = {"keys": keys, "labels": labels, "o": {}, "order": [o[0] for o in avail],
            "ramps": {"blue": seq_ramp(250.0), "green": seq_ramp(165.0)}, "div": div_ramp(),
            "nBoot": meta["model"]["n_boot"], "years": meta["years_used_rain"],
            "partial": meta.get("partial_year_excluded"), "last": meta["last_rain_date"]}
    heads = {}
    for key, short, name, noun, css, ramp in avail:
        o = J["outcomes"][key]
        dec = o["decendios"]
        pw = o["pairwise"]
        py = o["per_year"]
        dg = meta["diagnostics"][key]
        r4 = lambda v: None if v is None else round(v, 4)
        data["o"][key] = {
            "short": short, "name": name, "noun": noun, "css": css, "ramp": ramp,
            "mode": "min" if o["best_is"] == "lowest" else "max", "K": o["K"],
            "ib": keys.index(o["best_point"]), "iw": keys.index(o["worst_point"]),
            "ibr": keys.index(o["best_modal_raw"]),
            "nd": [x["n_days_window"] for x in dec],
            "pm": [x["p_model"] for x in dec], "pml": [x["p_model_boot90"][0] for x in dec],
            "pmh": [x["p_model_boot90"][1] for x in dec],
            "pr": [x["p_raw"] for x in dec], "prl": [x["p_raw_boot90"][0] for x in dec],
            "prh": [x["p_raw_boot90"][1] for x in dec],
            "pb": [x["P_best"] for x in dec], "pbr": [x["P_best_raw"] for x in dec],
            "pt3": [x["P_top3"] for x in dec], "pt3r": [x["P_top3_raw"] for x in dec],
            "tier": [x["tier"] for x in dec], "amb": [1 if x["tier_ambiguous"] else 0 for x in dec],
            "rdm": [x["rank_dist_model"] for x in dec], "rdr": [x["rank_dist_raw"] for x in dec],
            "rmm": [x["rank_median_model"] for x in dec], "rcm": [x["rank_ci90_model"] for x in dec],
            "rmr": [x["rank_median_raw"] for x in dec], "rcr": [x["rank_ci90_raw"] for x in dec],
            "pwr": pw["P_better_raw"], "pwm": pw["P_better_model"], "dif": pw["diff_raw"],
            "dci": pw["diff_raw_ci90"], "exz": [[1 if v else 0 for v in row] for row in pw["ci_excludes_zero"]],
            "py": {"years": py["years"], "partial": py["partial_year"], "count": py["count"], "n": py["n"],
                   "good": [{"label": g["label"], "op": g["op"], "k": g["k"], "share": g["share_years"],
                             "ci": g["wilson90"]} for g in py["good"]]},
            "cal": {"pin": dg["calibration"]["pred_in_sample"], "ploo": dg["calibration"]["pred_loyo"],
                    "obs": dg["calibration"]["obs"], "oci": dg["calibration"]["obs_boot90"]},
            "kt": [{"K": r["K"], "np": r["n_params"], "cv": r4(r["cv_logloss"]), "se": r4(r["cv_logloss_se"]),
                    "dv": r4(r["cv_diff_vs_min"]), "dse": r4(r["cv_diff_se"]), "aic": r["aic"], "bic": r["bic"]}
                   for r in dg["k_table"]],
            "kmin": {"cv": dg["K_min_cv"], "aic": dg["K_min_aic"], "bic": dg["K_min_bic"]},
            "rawcv": dg["raw_decendio_cv_logloss"],
            "pbk": o["P_best_by_K"],
        }
        heads[key] = headline(o, name, noun, labels)
        data["o"][key]["head"] = heads[key]

    # Título: trecho comum aos grupos "sem diferença do melhor" de chuva e céu aberto.
    def run_of(key):
        o = J["outcomes"][key]
        t1 = {j for j, x in enumerate(o["decendios"]) if x["tier"] == 1}
        return run_around(keys.index(o["best_point"]), t1)
    ra = run_of("rain")
    title = f"De abril a outubro, os decêndios de menos chuva vão de {labels[ra[0]]} a {labels[ra[1]]}"
    if "open" in J["outcomes"]:
        rb = run_of("open")
        a, b = max(ra[0], rb[0]), min(ra[1], rb[1])
        if a <= b:
            title = (f"De abril a outubro, menos chuva e mais céu aberto se encontram de {labels[a]} a {labels[b]}, "
                     f"e dentro desse trecho nenhum decêndio se destaca")
        else:
            title += ", e dentro desse trecho nenhum decêndio se destaca"
    else:
        title += ", e dentro desse trecho nenhum decêndio se destaca"

    pers = meta["persistence_rain_ge1mm"]
    y0, y1 = meta["years_used_rain"]
    partial = meta.get("partial_year_excluded")
    thr = meta.get("open_threshold_pct")
    lead = (f"Esta página compara os 21 decêndios de abril a outubro (dias 1–10, 11–20 e 21–fim de cada mês), "
            f"não só o melhor. Base: reanálise ERA5 em {meta['n_years_rain']} anos completos ({y0}–{y1})"
            f"{f'; {partial} é parcial e fica fora do modelo' if partial else ''}. "
            f"Toda a incerteza vem de {fmt(meta['model']['n_boot'])} réplicas bootstrap que sorteiam anos inteiros.")
    n_t1 = sum(1 for x in J["outcomes"]["rain"]["decendios"] if x["tier"] == 1) - 1
    caveat = ("<b>Leia antes do ranking.</b> A diferença entre decêndios vizinhos no meio do ano é menor que a variação "
              f"de um ano para outro. Na chuva ≥ 1 mm, o 1º colocado do modelo não se distingue de outros {n_t1} "
              "decêndios; por isso os gráficos mostram faixas, chances de cada posto e comparações par a par, não só o "
              "vencedor. Os níveis absolutos do ERA5 são altos demais para chuva fraca: use os números para comparar "
              "períodos, não como previsão.")

    # Robustez (tabela estática, todas as saídas)
    rows = meta["diagnostics"]["robustness_rows"]
    lab = dict(zip(keys, labels))
    out_name = {o[0]: o[1] for o in OUTCOMES}
    grp = {"split": "Metades da série", "threshold": "Limiar", "K": "Ordem harmônica",
           "cloud24h": "Nuvem de 24 h", "sunshine": "Insolação", "obs": "Observação"}
    trs = []
    for r in rows:
        sp = "–" if r["spearman"] is None else fmt(r["spearman"], 2).replace("-", "−")
        sh = "" if r.get("share_days_apr_oct") is None else f" ({pct(r['share_days_apr_oct'])} dos dias)"
        trs.append(f"<tr><td>{grp.get(r['group'], r['group'])}</td><td>{r['label']}{sh}</td>"
                   f"<td>{', '.join(lab[k] for k in (r['top3'] or []))}</td><td>{sp}</td></tr>")
    rob_tbl = ("<table><caption>Top 3 do ajuste em cada variação e correlação de postos (Spearman) dos 21 decêndios com "
               "o ajuste principal do mesmo desfecho (Galeão: com a proporção bruta do ERA5).</caption>"
               "<thead><tr><th>Verificação</th><th>Variação</th><th>Top 3</th><th>Spearman</th></tr></thead><tbody>"
               + "".join(trs) + "</tbody></table>")

    sun = [r for r in rows if r["group"] == "sunshine"]
    sun_txt = ""
    if sun:
        s06 = next((r for r in sun if "0,6" in r["label"]), sun[0])
        sq = sun[-1]
        sun_txt = (f"<b>Insolação descartada.</b> A fração de insolação do ERA5 (horas de sol / horas de luz) quase não "
                   f"acompanha a nebulosidade: com o corte de 0,6, {pct(s06['share_days_apr_oct'])} dos dias de abr–out "
                   f"seriam &ldquo;abertos&rdquo; e o ranking não tem relação com o de nuvem (Spearman "
                   f"{fmt(s06['spearman'], 2).replace('-', '−')}); escolhendo o corte para dar a mesma fração de dias "
                   f"abertos, o ranking se inverte (Spearman {fmt(sq['spearman'], 2).replace('-', '−')}). "
                   f"Por isso a página usa só a nebulosidade diurna.")
    gal = J["robustness"].get("ghcn_galeao_ge1mm")
    gal_txt = ""
    if gal:
        gp = [v for v in gal["p_raw"] if v is not None]
        gal_txt = (f"<b>Galeão (observação).</b> A estação GHCN do Galeão tem só parte dos dias (de "
                   f"{min(gal['n_obs'])} a {max(gal['n_obs'])} dias observados por decêndio, anos irregulares). "
                   f"Ela mostra níveis bem menores (de {pct(min(gp))} a {pct(max(gp))} de dias ≥ 1 mm por decêndio), "
                   f"coerente com o excesso de chuva fraca do ERA5, e o mesmo formato geral: correlação de postos "
                   f"{fmt(gal['spearman_vs_era5_raw'], 2)} com o ERA5 bruto; os três decêndios mais secos no Galeão são "
                   f"{', '.join(lab[k] for k in gal['top3'])}. É checagem de forma, não de nível.")

    pers_txt = (f"Dias chuvosos vêm em sequência: em abr–out, P(chuva | ontem choveu) = {pct(pers['p_rain_after_rain'])} contra "
                f"{pct(pers['p_rain_after_dry'])} se ontem foi seco; a variância das contagens por decêndio entre anos é, na "
                f"mediana, {fmt(pers['variance_inflation_median'], 1)} vez a binomial. Por isso o bootstrap sorteia anos "
                f"inteiros, e não dias.")

    open_def = (f"Céu aberto = nebulosidade média das 09 às 17 h de até {fmt(thr)}% (classe &ldquo;clear&rdquo; do "
                f"<a href=\"{NCEI_URL}\">NOAA/NCEI</a>, 0 a 3/10 de céu coberto). Dia bom = céu aberto e chuva &lt; 1 mm."
                if thr is not None else "")
    source = (f"Fonte: Open-Meteo, modelo ERA5, célula de grade de ~25 km (−22,75; −43,25); anos completos {y0}–{y1}, "
              f"dados até {fdate(meta['last_rain_date'])}"
              f"{f' ({partial} parcial, fora do modelo)' if partial else ''}. " + ATTR_HTML)

    tpl = open(TPL, encoding="utf-8").read()
    repl = {
        "TITLE": title, "LEAD": lead, "CAVEAT": caveat, "SOURCE": source, "ATTR": ATTR_HTML, "REPO": REPO,
        "DOC": DOC, "ROB_TBL": rob_tbl, "SUN_TXT": sun_txt, "GAL_TXT": gal_txt, "PERS_TXT": pers_txt,
        "OPEN_DEF": open_def, "NBOOT": fmt(meta["model"]["n_boot"]), "NY": str(meta["n_years_rain"]),
        "Y0": str(y0), "Y1": str(y1),
        "OUT_RADIOS": "".join(
            f'<label><input type="radio" name="out" value="{k}"{" checked" if i == 0 else ""}><span>{s}</span></label>'
            for i, (k, s, *_rest) in enumerate(avail)),
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
