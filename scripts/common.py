"""Funções de carga e agregação compartilhadas (somente biblioteca padrão).

API pública (todas puras, exceto as `load_*`, que leem arquivos em data/):

    load_daily(model="era5") -> list[(datetime.date, float | None)]
        Série diária de precipitação (mm). None = dia sem valor.
        model: "era5" (série principal, homogênea), "ecmwf_ifs" ou "best_match".
    load_meta() -> dict            # data/daily/meta.json
    load_refs() -> dict            # data/refs/refs.json (Alerta Rio, INMET)
    load_galeao() -> dict          # data/refs/galeao_ghcn.json

    complete_years(daily) -> list[int]
        Anos civis em que todos os dias têm valor (exclui anos parciais).
    last_valid_date(daily) -> datetime.date
    annual_stats(daily, thr=1.0, years=None) -> {ano: {"mm", "wet", "n"}}
        Total anual (mm), nº de dias com mm >= thr e nº de dias com valor.
        Se years=None usa os anos completos.
    monthly_stats(daily, years, thr=1.0) -> list[12 dict]
        Por mês: mm_mean, wet_mean (por ano), mm_share, wet_share (fração do
        total anual do período, agregado nos anos informados).
    slot_stats(daily, years, thr=1.0) -> dict {(mes, dia): {"n", "wet", "sum"}}
        Contagens por dia do calendário (inclui 29/fev) nos anos informados.
    quantile(xs, q) -> float       # interpolação linear (= numpy padrão)
    perm_diff_test(a, b, n_perm=20000, seed=1) -> (dif_médias, p)   # bilateral
    perm_trend_test(xs, ys, n_perm=20000, seed=1) -> (inclinação, p) # bilateral
    encode_tenths(daily) -> list[int]
        Décimos de mm como inteiros; -1 = ausente (formato embutido na página).

Nebulosidade e "dia de tempo aberto" (data/daily/era5_cloud.csv, mesma célula ERA5):

    load_cloud() -> list[(date, cloud24_pct, sunshine_min, daylight_min, cloud_day_pct)]
        Cada campo é None se vazio. cloud_day_pct = média da cobertura de nuvens das 09h às 17h locais.
    open_flags(cloud, thr=OPEN_THR) -> list[(date, bool | None)]
        Dia de tempo aberto = cobertura média diurna <= thr (%); None se sem dado.
        OPEN_THR = 30 corresponde ao "clear" (0 a 3/10) do NOAA/NCEI.
    rain_flags(daily, thr=1.0) -> list[(date, bool | None)]
    monthly_pct_by_year(flags, years) -> list[12] de list[% por ano]
        Para cada mês, a % de dias "verdadeiros" em cada ano (anos sem dado no mês são omitidos).
    monthly_summary(by_year) -> list[12 dict {mean, p10, p50, p90, n}] entre anos
    slot_flag_stats(flags, years) -> {(mes, dia): {"n", "yes"}}
    monthly_mean_cloud(cloud, years) -> list[12] média da nebulosidade diurna (%), entre dias
    sun_fraction_stats(cloud, years) -> dict: fração de sol (sunshine/daylight) e correlação com a nebulosidade
    encode_cloud_tenths(cloud) -> list[int]
        Décimos de % (0 a 1000) da nebulosidade diurna; -1 = ausente.
"""
import csv
import datetime as dt
import json
import math
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def load_daily(model="era5"):
    path = os.path.join(DATA, "daily", f"{model}.csv")
    out = []
    with open(path, encoding="utf-8", newline="") as f:
        r = csv.reader(f)
        next(r)
        for date_s, v in r:
            d = dt.date.fromisoformat(date_s)
            out.append((d, float(v) if v.strip() != "" else None))
    return out


def _json(*parts):
    with open(os.path.join(DATA, *parts), encoding="utf-8") as f:
        return json.load(f)


def load_meta():
    return _json("daily", "meta.json")


def load_refs():
    return _json("refs", "refs.json")


def load_galeao():
    return _json("refs", "galeao_ghcn.json")


def complete_years(daily):
    by = {}
    for d, v in daily:
        c = by.setdefault(d.year, [0, 0])
        c[0] += 1
        if v is not None:
            c[1] += 1
    return sorted(y for y, (tot, ok) in by.items() if tot == ok)


def last_valid_date(daily):
    return max(d for d, v in daily if v is not None)


def annual_stats(daily, thr=1.0, years=None):
    ys = set(years if years is not None else complete_years(daily))
    out = {}
    for d, v in daily:
        if d.year not in ys or v is None:
            continue
        s = out.setdefault(d.year, {"mm": 0.0, "wet": 0, "n": 0})
        s["mm"] += v
        s["n"] += 1
        if v >= thr:
            s["wet"] += 1
    return out


def monthly_stats(daily, years, thr=1.0):
    ys = set(years)
    mm = [0.0] * 12
    wet = [0] * 12
    for d, v in daily:
        if d.year in ys and v is not None:
            mm[d.month - 1] += v
            if v >= thr:
                wet[d.month - 1] += 1
    ny = len(ys)
    tm, tw = sum(mm), sum(wet)
    return [
        {"mm_mean": mm[i] / ny, "wet_mean": wet[i] / ny,
         "mm_share": mm[i] / tm, "wet_share": wet[i] / tw if tw else float("nan")}
        for i in range(12)
    ]


def slot_stats(daily, years, thr=1.0):
    ys = set(years)
    out = {}
    for d, v in daily:
        if d.year in ys and v is not None:
            s = out.setdefault((d.month, d.day), {"n": 0, "wet": 0, "sum": 0.0})
            s["n"] += 1
            s["sum"] += v
            if v >= thr:
                s["wet"] += 1
    return out


def quantile(xs, q):
    s = sorted(xs)
    if not s:
        return float("nan")
    h = (len(s) - 1) * q
    lo = math.floor(h)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (h - lo)


def perm_diff_test(a, b, n_perm=20000, seed=1):
    rng = random.Random(seed)
    obs = sum(a) / len(a) - sum(b) / len(b)
    pool = list(a) + list(b)
    na = len(a)
    hit = 0
    for _ in range(n_perm):
        rng.shuffle(pool)
        dif = sum(pool[:na]) / na - sum(pool[na:]) / (len(pool) - na)
        if abs(dif) >= abs(obs) - 1e-12:
            hit += 1
    return obs, (hit + 1) / (n_perm + 1)


def _slope(xs, ys):
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)


def perm_trend_test(xs, ys, n_perm=20000, seed=1):
    rng = random.Random(seed)
    obs = _slope(xs, ys)
    ys2 = list(ys)
    hit = 0
    for _ in range(n_perm):
        rng.shuffle(ys2)
        if abs(_slope(xs, ys2)) >= abs(obs) - 1e-12:
            hit += 1
    return obs, (hit + 1) / (n_perm + 1)


def encode_tenths(daily):
    return [-1 if v is None else int(round(v * 10)) for _, v in daily]


# ---------------------------------------------------------------- nebulosidade
NCEI_URL = "https://www.ncei.noaa.gov/products/land-based-station/comparative-climatic-data"
OPEN_THR = 30.0   # % de cobertura média diurna; "clear" = 0 a 3/10 (NOAA/NCEI Comparative Climatic Data)


def _opt(x):
    x = x.strip()
    return float(x) if x != "" else None


def load_cloud():
    path = os.path.join(DATA, "daily", "era5_cloud.csv")
    out = []
    with open(path, encoding="utf-8", newline="") as f:
        r = csv.reader(f)
        next(r)
        for row in r:
            out.append((dt.date.fromisoformat(row[0]), _opt(row[1]), _opt(row[2]), _opt(row[3]), _opt(row[4])))
    return out


def open_flags(cloud, thr=OPEN_THR):
    return [(c[0], None if c[4] is None else c[4] <= thr + 1e-9) for c in cloud]


def rain_flags(daily, thr=1.0):
    return [(d, None if v is None else v >= thr) for d, v in daily]


def monthly_pct_by_year(flags, years):
    ys = set(years)
    cnt = {}
    for d, f in flags:
        if d.year in ys and f is not None:
            c = cnt.setdefault((d.year, d.month), [0, 0])
            c[0] += 1
            c[1] += 1 if f else 0
    return [[100.0 * cnt[(y, m)][1] / cnt[(y, m)][0] for y in sorted(ys) if (y, m) in cnt] for m in range(1, 13)]


def monthly_summary(by_year):
    out = []
    for xs in by_year:
        out.append({"mean": sum(xs) / len(xs) if xs else float("nan"), "p10": quantile(xs, .1),
                    "p50": quantile(xs, .5), "p90": quantile(xs, .9), "n": len(xs)})
    return out


def slot_flag_stats(flags, years):
    ys = set(years)
    out = {}
    for d, f in flags:
        if d.year in ys and f is not None:
            s = out.setdefault((d.month, d.day), {"n": 0, "yes": 0})
            s["n"] += 1
            s["yes"] += 1 if f else 0
    return out


def monthly_mean_cloud(cloud, years):
    ys = set(years)
    s, n = [0.0] * 12, [0] * 12
    for c in cloud:
        if c[0].year in ys and c[4] is not None:
            s[c[0].month - 1] += c[4]
            n[c[0].month - 1] += 1
    return [s[i] / n[i] if n[i] else float("nan") for i in range(12)]


def sun_fraction_stats(cloud, years):
    """Fração de sol = sunshine/daylight por dia; correlação de Pearson com a nebulosidade diurna."""
    ys = set(years)
    xs, fs = [], []
    for c in cloud:
        if c[0].year in ys and c[4] is not None and c[2] is not None and c[3]:
            xs.append(c[4])
            fs.append(c[2] / c[3])
    mx, mf = sum(xs) / len(xs), sum(fs) / len(fs)
    cov = sum((a - mx) * (b - mf) for a, b in zip(xs, fs))
    r = cov / math.sqrt(sum((a - mx) ** 2 for a in xs) * sum((b - mf) ** 2 for b in fs))
    return {"n": len(xs), "mean_fraction": mf, "r": r}


def encode_cloud_tenths(cloud):
    return [-1 if c[4] is None else int(round(c[4] * 10)) for c in cloud]


def monthly_sun_fraction(cloud, years):
    """Média mensal da fração de insolação (sunshine/daylight) nos dias com valor."""
    ys = set(years)
    s, n = [0.0] * 12, [0] * 12
    for c in cloud:
        if c[0].year in ys and c[2] is not None and c[3]:
            s[c[0].month - 1] += c[2] / c[3]
            n[c[0].month - 1] += 1
    return [s[i] / n[i] if n[i] else float("nan") for i in range(12)]
