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
