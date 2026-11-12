#!/usr/bin/env python3
"""Gera site/index.html (página principal) a partir de data/. Só biblioteca padrão.

Uso: python3 scripts/build_main.py        (idempotente; sem timestamps)
"""
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

OUT = os.path.join(C.ROOT, "site", "index.html")
REPO = "https://github.com/joseluizn/chuva-rio"
ATTR_HTML = ('Dados: <a href="https://open-meteo.com/">Open-Meteo.com</a> '
             '(<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>), '
             'reanálise ERA5 — Copernicus/ECMWF. '
             'Nebulosidade e insolação: ERA5 via Open-Meteo, CC BY 4.0.')
NCEI_URL = C.NCEI_URL
MN = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def fmt(x, d=0):
    s = f"{x:,.{d}f}"
    return s.replace(",", "\u0000").replace(".", ",").replace("\u0000", ".")


# ---------------------------------------------------------------- cores (OKLab)
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


def _lum(rgb):
    def lin(v):
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _srgb(hexs):
    return [int(hexs[i:i + 2], 16) / 255 for i in (1, 3, 5)]


def make_ramps(n=9, hue=250.0, min_contrast=3.2):
    """Rampa sequencial de uma matiz em OKLab/OKLCH; baixo e alto têm >= min_contrast vs fundo."""
    surf = {"light": _srgb("#fcfcfb"), "dark": _srgb("#1a1a19")}
    # claro: extremo baixo = o mais claro que ainda tem contraste suficiente; alto escuro
    lo, hi = 0.40, 0.80
    for _ in range(40):
        mid = (lo + hi) / 2
        if _contrast(_oklch_to_srgb(mid, 0.10, hue), surf["light"]) >= min_contrast:
            lo = mid
        else:
            hi = mid
    L0 = lo
    light = [_oklch_to_srgb(L0 + (0.30 - L0) * i / (n - 1), 0.10 + 0.04 * math.sin(math.pi * i / (n - 1)), hue)
             for i in range(n)]
    # escuro: mesma direção do claro (pedido do usuário: azul mais escuro = mais chuva).
    # Baixo = azul pálido; alto = azul profundo, ainda distinguível da superfície escura.
    dark = [_oklch_to_srgb(0.92 + (0.42 - 0.92) * i / (n - 1), 0.05 + 0.11 * (i / (n - 1)), hue)
            for i in range(n)]
    for name, ramp in (("light", light), ("dark", dark)):
        assert _contrast(ramp[0], surf[name]) >= 3.0, (name, _contrast(ramp[0], surf[name]))
    return {"light": [_hex(c) for c in light], "dark": [_hex(c) for c in dark]}


# ---------------------------------------------------------------- fatos calculados
def facts():
    daily = C.load_daily("era5")
    meta = C.load_meta()
    refs = C.load_refs()
    gal = C.load_galeao()
    ys = C.complete_years(daily)
    y0, y1 = ys[0], ys[-1]
    st = C.annual_stats(daily, 1.0, ys)
    mm = {y: st[y]["mm"] for y in ys}
    mean_mm = sum(mm.values()) / len(ys)
    mean_wet = sum(st[y]["wet"] for y in ys) / len(ys)
    ar, inm = refs["alertario"], refs["inmet"]
    ys_ar = [y for y in ys if 1997 <= y <= 2024]
    mean_mm_ar = sum(mm[y] for y in ys_ar) / len(ys_ar)
    bias_mm = mean_mm_ar / ar["annual_mm"] - 1
    bias_mm_inm = mean_mm / inm["annual_mm"] - 1
    bias_wet = mean_wet / inm["annual_wet_days"] - 1
    ms = C.monthly_stats(daily, ys, 1.0)
    # janela de 5 meses consecutivos (circular) com maior participação no volume
    w0 = max(range(12), key=lambda s0: sum(ms[(s0 + k) % 12]["mm_share"] for k in range(5)))
    wet_months = [(w0 + k) % 12 for k in range(5)]
    share_mm = sum(ms[m]["mm_share"] for m in wet_months)
    share_wet = sum(ms[m]["wet_share"] for m in wet_months)
    order = sorted(range(12), key=lambda m: ms[m]["mm_mean"])
    dry = [order[0]] + [m for m in order[1:] if ms[m]["mm_mean"] - ms[order[0]]["mm_mean"] < 1.0]
    dry = sorted(dry)
    # diferenças de participação vs referências (pontos percentuais)
    def sh(v):
        t = sum(v)
        return [x / t for x in v]
    d_ar = max(abs(ms[m]["mm_share"] - sh(ar["monthly_mm"])[m]) for m in range(12)) * 100
    d_in = max(abs(ms[m]["mm_share"] - sh(inm["monthly_mm"])[m]) for m in range(12)) * 100
    d_iw = max(abs(ms[m]["wet_share"] - sh(inm["wet_days"])[m]) for m in range(12)) * 100
    # queda 1995-2009 vs 2010-2025
    a = [mm[y] for y in ys if y <= 2009]
    b = [mm[y] for y in ys if y >= 2010]
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    _, p_diff = C.perm_diff_test(a, b, 100000, seed=1)
    slope, p_tr = C.perm_trend_test(ys, [mm[y] for y in ys], 100000, seed=1)
    bm = C.load_daily("best_match")
    bm_st = C.annual_stats(bm, 1.0, ys)
    bma = sum(bm_st[y]["mm"] for y in ys if y <= 2009) / len(a)
    bmb = sum(bm_st[y]["mm"] for y in ys if y >= 2010) / len(b)
    ifs = C.load_daily("ecmwf_ifs")
    yi = [y for y in ys if y >= 2017]
    ifs_st = C.annual_stats(ifs, 1.0, yi)
    ifs_ratio = sum(ifs_st[y]["mm"] for y in yi) / sum(mm[y] for y in yi)
    # contraste sazonal vs Alerta Rio (período comum 1997..<=2024)
    ys_c = [y for y in ys if 1997 <= y <= 2024]
    mc = C.monthly_stats(daily, ys_c, 1.0)
    err = [mc[m]["mm_mean"] / ar["monthly_mm"][m] - 1 for m in range(12)]
    # 2026 (ano parcial) contra a normal na mesma data
    last_d = C.last_valid_date(daily)
    part_cum = norm_cum = None
    if last_d.year > ys[-1]:
        md = (last_d.month, last_d.day)
        part_cum = sum(v for d, v in daily if d.year == last_d.year and v is not None)
        cums = [sum(v for d, v in daily if d.year == y and (d.month, d.day) <= md and v is not None) for y in ys]
        norm_cum = C.quantile(cums, 0.5)
    # probabilidade suavizada (7 dias circular, ponderada por n), limiar 1 mm, anos completos
    sl = C.slot_stats(daily, ys, 1.0)
    keys = [(m, d) for m in range(1, 13) for d in range(1, [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1] + 1)]
    ps = []
    for i in range(366):
        nn = sum(sl[keys[(i + k) % 366]]["n"] for k in range(-3, 4))
        ww = sum(sl[keys[(i + k) % 366]]["wet"] for k in range(-3, 4))
        ps.append(ww / nn)
    imax = max(range(366), key=lambda i: ps[i])
    imin = min(range(366), key=lambda i: ps[i])
    # razão de ruído (sem tendência linear dentro do mês), mesma definição da página
    o2 = e2 = 0.0
    for m in range(1, 13):
        ks = [k for k in keys if k[0] == m and k != (2, 29)]
        D = len(ks)
        W = sum(sl[k]["wet"] for k in ks)
        Nn = sum(sl[k]["n"] for k in ks)
        pb = W / Nn
        pv = [sl[k]["wet"] / sl[k]["n"] for k in ks]
        xm = (D - 1) / 2
        pm = sum(pv) / D
        b = sum((i - xm) * (pv[i] - pm) for i in range(D)) / sum((i - xm) ** 2 for i in range(D))
        o2 += sum((pv[i] - (pm + b * (i - xm))) ** 2 for i in range(D))
        e2 += sum(pb * (1 - pb) / sl[k]["n"] for k in ks) * (D - 2) / D
    noise_r2 = o2 / e2
    # Galeão
    g = {}
    for yy in ("2020", "2021"):
        s = C.annual_stats(daily, 1.0, [int(yy)])[int(yy)]
        g[yy] = dict(obs_mm=gal["years"][yy]["total_mm"], obs_wet=gal["years"][yy]["wet_days_ge1"],
                     era_mm=s["mm"], era_wet=s["wet"])
    last = C.last_valid_date(daily)
    n29 = sum(1 for y in ys if y % 4 == 0)
    cl = C.load_cloud()
    assert len(cl) == len(daily) and all(a[0] == b[0] for a, b in zip(cl, daily)), "nuvem e chuva desalinhadas"
    of = C.open_flags(cl)
    by_open = C.monthly_summary(C.monthly_pct_by_year(of, ys))
    by_wet = C.monthly_summary(C.monthly_pct_by_year(C.rain_flags(daily, 1.0), ys))
    ysx = set(ys)
    nopen = sum(1 for d, f in of if d.year in ysx and f)
    nval = sum(1 for d, f in of if d.year in ysx and f is not None)
    cloudf = dict(cl=cl, by_open=by_open, by_wet=by_wet, mcloud=C.monthly_mean_cloud(cl, ys),
                  open_all=nopen / nval, sun=C.sun_fraction_stats(cl, ys), msun=C.monthly_sun_fraction(cl, ys))
    return dict(cloud=cloudf, daily=daily, meta=meta, refs=refs, ys=ys, y0=y0, y1=y1, mean_mm=mean_mm, mean_wet=mean_wet,
                bias_mm=bias_mm, bias_mm_inm=bias_mm_inm, bias_wet=bias_wet, share_mm=share_mm,
                share_wet=share_wet, dry=dry, wet_months=wet_months, d_ar=d_ar, d_in=d_in, d_iw=d_iw, ma=ma, mb=mb,
                drop=mb / ma - 1, p_diff=p_diff, p_tr=p_tr, bm_drop=bmb / bma - 1, gal=g, last=last, ifs_ratio=ifs_ratio, err=err, ys_c=ys_c, part_cum=part_cum, norm_cum=norm_cum,
                keys=keys, ps=ps, imax=imax, imin=imin, noise_r2=noise_r2, last_d=last_d, n29=n29,
                ms=ms)


def mlist(ms_):
    names = [MN[m] for m in ms_]
    if len(ms_) == 2 and ms_[1] == ms_[0] + 1:
        return f"{names[0]}–{names[1]}"
    return " e ".join(names)


def fdate(d):
    return f"{d.day}/{MN[d.month - 1]}/{d.year}"


def pct(x, d=0, sign=False):
    s = fmt(abs(x) * 100, d)
    if sign:
        return ("+" if x >= 0 else "−") + s + "%"
    return s + "%"


def pval(p):
    return fmt(p, 3)


# ---------------------------------------------------------------- modelo por decêndio (abr-out)
PER_JSON = os.path.join(C.ROOT, "data", "derived", "periodos_abr_out.json")
PER_OUT = [("rain", "Chuva (≥ 1 mm)", "dias chuvosos", "min"),
           ("open", "Céu aberto", "dias de céu aberto", "max"),
           ("bom", "Dia bom (aberto e seco)", "dias bons", "max")]


def _run_around(idx, members):
    """Trecho contíguo de índices (em ordem de calendário) que contém idx, dentro de members."""
    a = b = idx
    while a - 1 in members:
        a -= 1
    while b + 1 in members:
        b += 1
    return a, b


def period_data():
    """Lê o JSON do modelo por decêndio e devolve (dict compacto para a página, texto do limiar) ou (None, None)."""
    if not os.path.exists(PER_JSON):
        print("AVISO: data/derived/periodos_abr_out.json não existe; seção do modelo omitida.", file=sys.stderr)
        return None, None
    d = json.load(open(PER_JSON, encoding="utf-8"))
    out = {"keys": [], "labels": [], "nd": [], "o": {}}
    thr_model = d["meta"].get("open_threshold_pct")
    if thr_model is None:
        m = re.search(r"<=\s*([0-9.]+)\s*%", d["meta"]["definitions"]["open"])
        thr_model = float(m.group(1)) if m else None
    if thr_model is not None and abs(thr_model - C.OPEN_THR) > 1e-9:
        print(f"AVISO: o JSON do modelo usa céu aberto <= {thr_model}% e a página usa <= {C.OPEN_THR}%.", file=sys.stderr)
    for key, name, noun, mode in PER_OUT:
        o = d["outcomes"][key]
        dec = o["decendios"]
        keys = [x["key"] for x in dec]
        if not out["keys"]:
            out["keys"] = keys
            out["labels"] = [x["label"] for x in dec]
            out["nd"] = [x["n_days_window"] for x in dec]
        assert keys == out["keys"]
        ib = keys.index(o["best_point"])
        tied = {keys.index(k) for k in o["within_noise_of_best"]}
        a, b = _run_around(ib, tied | {ib})
        ibr = keys.index(o["best_modal_raw"])
        pm = [x["p_model"] for x in dec]
        worst = max(range(21), key=lambda i: pm[i]) if mode == "min" else min(range(21), key=lambda i: pm[i])
        lab = out["labels"]
        lab = out["labels"]
        run_n = b - a + 1
        ext = "mínimo" if mode == "min" else "máximo"
        pbr_max = max(x["P_best_raw"] for x in dec)
        head = (f"{name}: o modelo põe o {ext} em {lab[ib]}, com {pct(pm[ib])} de {noun} "
                f"(~{fmt(dec[ib]['expected_days'], 1)} dias em {dec[ib]['n_days_window']}); esse é o centro da curva suave "
                f"(melhor em {pct(dec[ib]['P_best'])} das réplicas bootstrap). ")
        if run_n > 1:
            head += (f"A curva é plana em torno do melhor: de {lab[a]} a {lab[b]}, {run_n} decêndios consecutivos não se distinguem de "
                     f"{lab[ib]} (diferença bruta pareada com IC 90% que inclui zero), e sem impor forma à curva nenhum "
                     f"decêndio passa de {pct(pbr_max)} de chance de ser o melhor. ")
        else:
            head += (f"Sem impor forma à curva, nenhum decêndio passa de {pct(pbr_max)} de chance de ser o melhor. ")
        extra = len(tied) - (run_n - 1)
        if extra > 0:
            head += (f"Mais {extra} {'período fora' if extra == 1 else 'períodos fora'} desse trecho também não se "
                     f"{'distingue' if extra == 1 else 'distinguem'} do melhor. ")
        head += f"O extremo oposto é {lab[worst]}, com {pct(pm[worst])} de {noun}."
        out["o"][key] = {
            "name": name, "mode": mode, "noun": noun, "ib": ib, "ibr": ibr, "K": o["K"], "head": head,
            "run": [a, b], "tied": sorted(tied),
            "pm": pm, "pml": [x["p_model_boot90"][0] for x in dec], "pmh": [x["p_model_boot90"][1] for x in dec],
            "pr": [x["p_raw"] for x in dec], "prl": [x["p_raw_boot90"][0] for x in dec],
            "prh": [x["p_raw_boot90"][1] for x in dec], "ed": [x["expected_days"] for x in dec],
            "pb": [x["P_best"] for x in dec], "pbr": [x["P_best_raw"] for x in dec],
            "pt3": [x["P_top3_raw"] for x in dec], "n": [x["n_obs"] for x in dec],
        }
    o5 = d["outcomes"]["rain_ge5mm"]
    k5 = [x["key"] for x in o5["decendios"]]
    l5 = {x["key"]: x["label"] for x in o5["decendios"]}
    out["ge5"] = {"best": l5[o5["best_point"]], "best_raw": l5[o5["best_modal_raw"]],
                  "p_best_raw": [x["P_best_raw"] for x in o5["decendios"] if x["key"] == o5["best_modal_raw"]][0],
                  "p_raw": [x["p_raw"] for x in o5["decendios"] if x["key"] == o5["best_modal_raw"]][0]}
    meta = d["meta"]
    out["meta"] = {"n_boot": meta["model"]["n_boot"], "years": meta["years_used_rain"], "n_years": meta["n_years_rain"],
                   "last": meta["last_rain_date"], "thr_model": thr_model,
                   "pers_after_rain": meta["persistence_rain_ge1mm"]["p_rain_after_rain"],
                   "pers_after_dry": meta["persistence_rain_ge1mm"]["p_rain_after_dry"],
                   "vif": meta["persistence_rain_ge1mm"]["variance_inflation_median"],
                   "K": {k: out["o"][k]["K"] for k in out["o"]}}
    return out, thr_model


def build():
    F = facts()
    meta = F["meta"]
    era = meta["models"]["era5"]
    last = F["last"]
    ramps = make_ramps()
    tenths = C.encode_tenths(F["daily"])
    refs = F["refs"]
    n_y = len(F["ys"])
    y0, y1 = F["y0"], F["y1"]
    dry = mlist(F["dry"])
    gal = F["gal"]

    wm = F["wet_months"]
    FULL = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
            "novembro", "dezembro"]
    season = f"de {FULL[wm[0]]} a {FULL[wm[-1]]}"
    mw = F["ms"]
    order_w = sorted(range(12), key=lambda m: -mw[m]["mm_mean"])
    wetm = sorted([order_w[0]] + [m for m in order_w[1:] if mw[order_w[0]]["mm_mean"] - mw[m]["mm_mean"] < 1.0])
    ctr_mm = max(x["mm_share"] for x in mw) / min(x["mm_share"] for x in mw)
    ctr_wet = max(x["wet_share"] for x in mw) / min(x["wet_share"] for x in mw)
    stronger = F["share_mm"] > F["share_wet"]
    title = (f"A chuva no Rio se concentra {season}"
             + (": nesses meses chove mais vezes e, sobretudo, mais forte" if stronger else ""))
    kd = lambda i: f"{F['keys'][i][1]}/{MN[F['keys'][i][0] - 1]}"
    lead1 = (f"Em média, o ERA5 registra {fmt(F['mean_mm'])} mm e {fmt(F['mean_wet'])} dias com ≥ 1 mm por ano ({y0}–{y1}). "
             f"O período {season} concentra {pct(F['share_mm'])} do volume e {pct(F['share_wet'])} dos dias chuvosos.")
    fulls = lambda l: " e ".join(FULL[m] for m in l)
    lead2 = (f"{fulls(wetm).capitalize()} {'é o mês mais chuvoso' if len(wetm) == 1 else 'são os meses mais chuvosos'} e "
             f"{fulls(F['dry'])} {'é o mais seco' if len(F['dry']) == 1 else 'são os mais secos'}; o contraste entre o mês mais e o menos "
             f"chuvoso é de {fmt(ctr_mm, 1)}× no volume e de {fmt(ctr_wet, 1)}× nos dias chuvosos.")
    if F["part_cum"] is not None:
        lead3 = (f"{F['last_d'].year} acumula {fmt(F['part_cum'])} mm até {F['last_d'].day}/{MN[F['last_d'].month - 1]}, "
                 f"{fmt(100 * F['part_cum'] / F['norm_cum'])}% da mediana dos anos completos na mesma data.")
    else:
        lead3 = f"{y1} foi o último ano completo da série."
    lead4 = (f"Dentro do ano, a probabilidade suavizada de dia chuvoso vai de {pct(F['ps'][F['imax']])} (em {kd(F['imax'])}) "
             f"a {pct(F['ps'][F['imin']])} (em {kd(F['imin'])}); " +
             ("fora desse gradiente sazonal, as diferenças entre dias vizinhos são compatíveis com acaso."
              if F["noise_r2"] < 1.25 else "há também variação entre dias vizinhos além do esperado por acaso."))
    verdict = ("sugestiva, não conclusiva" if max(F["p_diff"], F["p_tr"]) >= 0.05
               else "consistente nos dois testes, mas de uma única célula")
    e = F["err"]
    emax = max(range(12), key=lambda m: e[m])
    emin = min(range(12), key=lambda m: e[m])
    def runs(ms_):
        ms_ = sorted(ms_)
        if not ms_:
            return "nenhum mês"
        out, cur = [], [ms_[0]]
        for m in ms_[1:]:
            if m == cur[-1] + 1:
                cur.append(m)
            else:
                out.append(cur)
                cur = [m]
        out.append(cur)
        if len(out) > 1 and out[0][0] == 0 and out[-1][-1] == 11:
            out[0] = out[-1] + out[0]
            out.pop()
        return " e ".join(MN[r[0]] if len(r) == 1 else f"{MN[r[0]]}–{MN[r[-1]]}" for r in out)
    biastxt = (f"Frente ao Alerta Rio (média de 33 pluviômetros, 1997–2024), o ERA5 superestima o volume em cerca de "
               f"{pct(F['bias_mm'])}; frente ao INMET, a frequência em cerca de {pct(F['bias_wet'])} "
               f"({fmt(F['mean_wet'])} contra {refs['inmet']['annual_wet_days']} dias ≥ 1 mm por ano). As participações mensais "
               f"do ERA5 ficam a até {fmt(max(F['d_ar'], F['d_in'], F['d_iw']), 1)} pontos percentuais das referências, mas o "
               f"ERA5 exagera o contraste sazonal: contra o Alerta Rio, no período comum {F['ys_c'][0]}–{F['ys_c'][-1]}, o erro "
               f"relativo do volume mensal vai de {pct(e[emax], 0, True)} em {MN[emax]} a {pct(e[emin], 0, True)} em {MN[emin]}; "
               f"é positivo em {runs([m for m in range(12) if e[m] > 0])} e negativo em {runs([m for m in range(12) if e[m] < 0])}.")
    import datetime as _dt
    partial = [y for y in range(y1 + 1, last.year + 1)]
    ptxt = (f"{last.year} é parcial e fica fora das médias" if last.year > y1
            else "todos os anos são completos")
    sourceline = (f"Fonte: Open-Meteo, modelo ERA5, célula de grade de ~25 km; {fdate(_dt.date(y0, 1, 1))} a {fdate(last)}"
                  f"{'' if last.year == y1 else f' ({last.year} parcial, fora das médias)'}. " + ATTR_HTML)

    static = {
        "ar": refs["alertario"]["monthly_mm"], "ar_annual": refs["alertario"]["annual_mm"],
        "inm": refs["inmet"]["monthly_mm"], "inm_annual": refs["inmet"]["annual_mm"],
        "inm_wet": refs["inmet"]["wet_days"], "inm_wet_annual": refs["inmet"]["annual_wet_days"],
        "ramps": ramps, "y1": y1, "ymin": y0,
        "lastIdx": max(i for i, v in enumerate(tenths) if v >= 0),
    }

    # nota sobre a queda (calculada)
    n_a = len([y for y in F["ys"] if y <= 2009])
    n_b = len([y for y in F["ys"] if y >= 2010])
    verdict = ("sugestiva, não conclusiva" if max(F["p_diff"], F["p_tr"]) >= 0.05
               else "consistente nos dois testes, mas de uma única célula")
    note_drop = (
        f"No ERA5 homogêneo, a média anual cai de {fmt(F['ma'])} mm (1995–2009, {n_a} anos) para {fmt(F['mb'])} mm "
        f"(2010–{y1}, {n_b} anos): {pct(F['drop'], 0, True)} (teste de permutação da diferença de médias, p = {pval(F['p_diff'])}; "
        f"tendência linear {y0}–{y1}, p = {pval(F['p_tr'])}). Leitura: {verdict} (uma única célula e "
        f"alta variabilidade entre anos). Com o modelo padrão do Open-Meteo (best_match), que troca de ERA5 para ECMWF IFS em "
        f"2017-01-01, a mesma comparação daria {pct(F['bm_drop'], 0, True)}: queda exagerada, em boa parte artefato da troca de produto."
    )

    galline = "; ".join(
        f"{a}: observado {fmt(g['obs_mm'])} mm e {g['obs_wet']} dias, ERA5 {fmt(g['era_mm'])} mm e {g['era_wet']} dias"
        for a, g in gal.items())

    # ---- dias de tempo aberto
    CF = F["cloud"]
    thr_open = C.OPEN_THR
    mo, mw_ = CF["by_open"], CF["by_wet"]
    hi = max(range(12), key=lambda m: mo[m]["mean"])
    lo = min(range(12), key=lambda m: mo[m]["mean"])
    cl_last = max(c[0] for c in CF["cl"] if c[4] is not None)
    open_head = (f"Em {y0}–{y1}, {pct(CF['open_all'])} dos dias do ERA5 têm céu aberto (nebulosidade média das 09 às 17 h de até "
                 f"{fmt(thr_open)}%). {FULL[hi].capitalize()} é o mês mais aberto, com {pct(mo[hi]['mean'] / 100)} dos dias "
                 f"(faixa p10–p90 entre anos: {fmt(mo[hi]['p10'])}–{fmt(mo[hi]['p90'])}%), e {FULL[lo]} o menos aberto, com "
                 f"{pct(mo[lo]['mean'] / 100)} ({fmt(mo[lo]['p10'])}–{fmt(mo[lo]['p90'])}%); nesses meses, {pct(mw_[hi]['mean'] / 100)} "
                 f"e {pct(mw_[lo]['mean'] / 100)} dos dias têm chuva ≥ 1 mm.")
    sun = CF["sun"]
    ms_ = [x for x in CF["msun"]]
    open_note = (f"<b>Dias de tempo aberto.</b> Nebulosidade: variável horária <code>cloud_cover</code> (cobertura total de nuvens, %) "
                 f"do ERA5 via Open-Meteo, na mesma célula da chuva; dados até {fdate(cl_last)}. Dia de tempo aberto = média das 9 horas locais "
                 f"de 09 a 17 h de até {fmt(thr_open)}%, que corresponde à classe &ldquo;clear&rdquo; do NOAA/NCEI (cobertura média do céu de 0 a 3/10 "
                 f"nas horas de luz; parcialmente nublado é 4–7/10 e nublado 8–10/10; "
                 f"<a href=\"{NCEI_URL}\">Comparative Climatic Data</a>). Usei a média diurna, e não a de 24 h, porque esta inclui a noite. "
                 f"O limiar é convencional; a versão completa permite variá-lo. A nebulosidade do ERA5 é saída de modelo, não observação, e não "
                 f"achei referência observada para conferi-la: os percentuais servem para comparar meses e datas entre si, não como "
                 f"frequência observada de dias claros. Os totais por mês usam os anos completos; cada ponto do gráfico mensal é a "
                 f"porcentagem de dias abertos de um ano, e a mediana e a faixa p10–p90 são calculadas entre anos (interpolação linear). "
                 f"Insolação checada e descartada: a fração de insolação do ERA5 (<code>sunshine_duration</code> / <code>daylight_duration</code>) "
                 f"é quase constante no ano (médias mensais de {fmt(min(ms_), 2)} a {fmt(max(ms_), 2)}; média geral {fmt(sun['mean_fraction'], 2)}) e "
                 f"correlaciona só r = {fmt(sun['r'], 2)} com a nebulosidade diurna diária; o ranking dos decêndios por insolação inverte o da "
                 f"nebulosidade (ver <a href=\"{REPO}/blob/main/docs/modelo_periodos.md\">docs/modelo_periodos.md</a>). Por isso a página usa só a nebulosidade.")
    PD, thr_model = period_data()
    per_note = ""
    if PD:
        mt = PD["meta"]
        kk = mt["K"]
        g5 = PD["ge5"]
        diff_thr = (f" No JSON do modelo, &ldquo;aberto&rdquo; usa limiar de {fmt(mt['thr_model'], 1)}%, diferente do {fmt(thr_open)}% desta página."
                    if mt["thr_model"] is not None and abs(mt["thr_model"] - thr_open) > 1e-9 else "")
        per_note = (f"<b>Modelo por decêndio (abril a outubro).</b> Regressão logística da probabilidade diária com K pares de Fourier "
                    f"(K = {kk['rain']} para chuva, {kk['open']} para céu aberto e {kk['bom']} para dia bom, escolhido por validação cruzada deixando um ano "
                    f"de fora, menor K a até 1 erro-padrão do mínimo), ajustada no ano inteiro; a probabilidade do decêndio é a média das probabilidades "
                    f"diárias. Faixas de 90% por bootstrap de {fmt(mt['n_boot'])} réplicas de anos inteiros, que preserva a dependência entre dias "
                    f"(P(chuva | ontem choveu) = {pct(mt['pers_after_rain'])}, contra {pct(mt['pers_after_dry'])} se ontem foi seco). "
                    f"Dia bom = céu aberto e chuva &lt; 1 mm. &ldquo;Melhor&rdquo; = decêndio de menor chuva ou de mais céu aberto. Com K pequeno a curva é "
                    f"uma senoide e o P(melhor) do modelo mede a incerteza do <i>centro</i> da curva, não de um decêndio específico; por isso o gráfico mostra também o "
                    f"P(melhor) sem impor forma, com as proporções brutas. &ldquo;Sem diferença distinguível&rdquo; = o IC 90% pareado da diferença bruta para o melhor inclui zero. "
                    f"Com chuva ≥ 5 mm, o centro do modelo fica em {g5['best']}, e sem impor forma o decêndio mais provável como melhor é {g5['best_raw']} "
                    f"({pct(g5['p_raw'])} dos dias, melhor em {pct(g5['p_best_raw'])} das réplicas).{diff_thr} "
                    f"Escolhas de método (K, regra de 1 EP, diferenças pareadas) são julgamentos meus; detalhes e limitações em "
                    f"<a href=\"{REPO}/blob/main/docs/modelo_periodos.md\">docs/modelo_periodos.md</a>.")
    cl_tenths = C.encode_cloud_tenths(F["cloud"]["cl"])
    ramps_open = make_ramps(hue=165.0)
    static["rampsOpen"] = ramps_open
    static["openThr"] = thr_open
    static["per"] = PD
    tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "main_template.html"), encoding="utf-8").read()
    repl = {
        "OPEN_HEAD": open_head, "OPEN_NOTE": open_note, "PER_NOTE": per_note, "OPENTHR": fmt(thr_open),
        "CLOUD": ",".join(str(v) for v in cl_tenths),
        "TITLE": title, "LEAD1": lead1, "LEAD2": lead2, "LEAD3": lead3, "LEAD4": lead4, "BIASTXT": biastxt, "SOURCELINE": sourceline,
        "NOTE_DROP": note_drop, "STATIC": json.dumps(static, ensure_ascii=False, separators=(",", ":")),
        "TENTHS": ",".join(str(v) for v in tenths),
        "ERA5_URL": era["url"], "ERA5_LAT": fmt(era["returned_latitude"], 2).replace("-", "−"), "ERA5_LON": fmt(era["returned_longitude"], 2).replace("-", "−"),
        "ELEV": str(era.get("elevation_m", "")), "ACCESSED": meta["accessed"], "LAST": fdate(last),
        "Y0": str(y0), "Y1": str(y1), "NY": str(n_y), "N29": str(F["n29"]), "GALLINE": galline,
        "BIAS_MM": pct(F["bias_mm"]), "BIAS_WET": pct(F["bias_wet"]), "BIAS_MM_INM": pct(F["bias_mm_inm"]),
        "AR_ANNUAL": fmt(refs["alertario"]["annual_mm"]), "INM_ANNUAL": fmt(refs["inmet"]["annual_mm"], 0),
        "INM_WET": str(refs["inmet"]["annual_wet_days"]), "AR_URL": refs["alertario"]["url"],
        "INM_URL": refs["inmet"]["url"], "INM_PERIOD": refs["inmet"]["period_note"], "REPO": REPO,
        "ATTR": ATTR_HTML, "IFS_PCT": pct(F["ifs_ratio"]), "MEAN_MM": fmt(F["mean_mm"]), "MEAN_WET": fmt(F["mean_wet"]),
    }
    for k, v in repl.items():
        tpl = tpl.replace(f"%%{k}%%", v)
    # paleta de rampas em CSS não é necessária (JS usa static.ramps)
    left = re.findall(r"%%[A-Z0-9_]+%%", tpl)
    if left:
        sys.exit(f"marcadores sem valor: {set(left)}")
    # rampas
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(tpl)
    print(f"escrito {OUT} ({len(tpl) / 1024:.0f} KB)")


if __name__ == "__main__":
    build()
