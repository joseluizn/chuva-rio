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
             'reanálise ERA5 — Copernicus/ECMWF.')
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
    # Galeão
    g = {}
    for yy in ("2020", "2021"):
        s = C.annual_stats(daily, 1.0, [int(yy)])[int(yy)]
        g[yy] = dict(obs_mm=gal["years"][yy]["total_mm"], obs_wet=gal["years"][yy]["wet_days_ge1"],
                     era_mm=s["mm"], era_wet=s["wet"])
    last = C.last_valid_date(daily)
    n29 = sum(1 for y in ys if y % 4 == 0)
    return dict(daily=daily, meta=meta, refs=refs, ys=ys, y0=y0, y1=y1, mean_mm=mean_mm, mean_wet=mean_wet,
                bias_mm=bias_mm, bias_mm_inm=bias_mm_inm, bias_wet=bias_wet, share_mm=share_mm,
                share_wet=share_wet, dry=dry, wet_months=wet_months, d_ar=d_ar, d_in=d_in, d_iw=d_iw, ma=ma, mb=mb,
                drop=mb / ma - 1, p_diff=p_diff, p_tr=p_tr, bm_drop=bmb / bma - 1, gal=g, last=last, ifs_ratio=ifs_ratio, n29=n29,
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
    title = (f"A chuva no Rio se concentra {season}; o ERA5 acerta o calendário, "
             "mas superestima o volume e a frequência")
    verdict = ("sugestivo, não conclusivo" if max(F["p_diff"], F["p_tr"]) >= 0.05
               else "consistente nos dois testes, mas de uma única célula")
    lead1 = (f"Entre {y0} e {y1}, o ERA5 (reanálise em célula de ~25 km) dá {fmt(F['mean_mm'])} mm por ano e "
             f"{fmt(F['mean_wet'])} dias com ≥ 1 mm. Frente a pluviômetros, ele superestima o volume em cerca de "
             f"{pct(F['bias_mm'])} (Alerta Rio, 1997–2024: {fmt(refs['alertario']['annual_mm'])} mm) e a frequência em "
             f"cerca de {pct(F['bias_wet'])} (INMET: {refs['inmet']['annual_wet_days']} dias).")
    lead2 = (f"O padrão sazonal relativo é o que se aproveita: {season} caem {pct(F['share_mm'])} do volume e "
             f"{pct(F['share_wet'])} dos dias chuvosos, e {dry} são os meses mais secos; as participações mensais ficam a "
             f"até {fmt(max(F['d_ar'], F['d_in'], F['d_iw']), 1)} pontos percentuais das referências observadas.")
    lead3 = (f"A média anual {'cai' if F['drop'] < 0 else 'sobe'} {pct(abs(F['drop']))} de 1995–2009 para 2010–{y1}: {verdict} "
             f"(p = {pval(F['p_diff'])} na diferença de médias; {pval(F['p_tr'])} na tendência linear).")
    import datetime as _dt
    partial = [y for y in range(y1 + 1, last.year + 1)]
    ptxt = (f"{last.year} é parcial e fica fora das médias" if last.year > y1
            else "todos os anos são completos")
    sourceline = (f"Fonte: Open-Meteo Historical Weather API, modelo ERA5. Célula de grade em "
                  f"{fmt(era['returned_latitude'], 2).replace('-', '−')}; {fmt(era['returned_longitude'], 2).replace('-', '−')} "
                  f"(ponto pedido: −22,9068; −43,1729). Período {fdate(_dt.date(y0, 1, 1))} a {fdate(last)}; {ptxt}. "
                  f"Consulta em {meta['accessed']}. " + ATTR_HTML)

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

    tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "main_template.html"), encoding="utf-8").read()
    repl = {
        "TITLE": title, "LEAD1": lead1, "LEAD2": lead2, "LEAD3": lead3, "SOURCELINE": sourceline,
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
