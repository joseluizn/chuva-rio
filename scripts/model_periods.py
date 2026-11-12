"""Modelo de períodos (decêndios) abril–outubro: menor chance de chuva e maior
chance de dia aberto (pouca nuvem) no Rio de Janeiro.

Somente biblioteca padrão (roda na GitHub Action sem dependências).
Idempotente: sementes fixas e `generated_at` = última data com dado (não o
relógio). Lê data/daily/era5.csv (chuva) e, se existir,
data/daily/era5_cloud.csv (nuvem/insolação); grava
data/derived/periodos_abr_out.json.

Método (detalhes em docs/modelo_periodos.md):
  * Desfecho diário binário (chuva >= 1 mm; >= 5 mm como sensibilidade;
    "aberto"; "bom" = aberto e < 1 mm).
  * Regressão logística no dia do ano com K pares de Fourier, ajustada no ano
    inteiro (bordas abr/out sem artefato), por IRLS/Newton em dados agregados
    por dia do calendário (estatística suficiente: o preditor só depende do dia).
  * K escolhido por log-loss com validação deixando um ano de fora (LOYO),
    avaliada só nos dias abr–out; AIC reportado ao lado.
  * Incerteza: bootstrap em blocos de ANOS inteiros (reamostra anos com
    reposição), que preserva a persistência dentro do ano.
  * Por decêndio: probabilidade média do modelo, IC 90% percentil, P(melhor),
    P(top 3), diferença para o melhor com IC; proporção bruta com IC de Wilson.

Uso: python scripts/model_periods.py [--boot N]
"""
import argparse
import csv
import datetime as dt
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import OPEN_THR  # noqa: E402  limiar de dia aberto do site (% nuvem diurna)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAILY = os.path.join(ROOT, "data", "daily")
OUT = os.path.join(ROOT, "data", "derived", "periodos_abr_out.json")
GHCN = os.path.join(ROOT, "data", "refs", "ghcn_BRM00083746_1995_2025.csv")

SEED = 20261112
N_BOOT = 1000
K_MAX = 6
Z90 = 1.6448536269514722
SPLIT_YEAR = 2010  # amostra 1: anos <= 2010; amostra 2: anos > 2010

MONTHS = [(4, "abr"), (5, "mai"), (6, "jun"), (7, "jul"), (8, "ago"),
          (9, "set"), (10, "out")]
MONTH_LEN = {4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31}

# Índice de calendário 0..365 num ano bissexto de referência (29/fev = 59).
_REF = dt.date(2000, 1, 1)


def cal_index(month, day):
    return (dt.date(2000, month, day) - _REF).days


NCAL = 366


def decendios():
    out = []
    for m, ab in MONTHS:
        for j, (a, b) in enumerate([(1, 10), (11, 20), (21, MONTH_LEN[m])]):
            out.append({
                "key": "%s-%d" % (ab, j + 1),
                "label": "%s %d–%d" % (ab, a, b),
                "month": m, "dec": j + 1, "day_from": a, "day_to": b,
                "idx": [cal_index(m, d) for d in range(a, b + 1)],
            })
    return out


DECS = decendios()
SEASON_IDX = [i for d in DECS for i in d["idx"]]


# --------------------------------------------------------------------- dados
def read_csv_cols(path):
    with open(path, newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        rows = list(rd)
        return rd.fieldnames, rows


def fnum(s):
    s = (s or "").strip()
    return None if s == "" else float(s)


def load_rain():
    _, rows = read_csv_cols(os.path.join(DAILY, "era5.csv"))
    return {dt.date.fromisoformat(r["date"]): fnum(r["precip_mm"]) for r in rows}


def load_cloud():
    """Devolve (dados, descrição) ou (None, motivo)."""
    path = os.path.join(DAILY, "era5_cloud.csv")
    if not os.path.exists(path):
        return None, "data/daily/era5_cloud.csv ausente"
    fields, rows = read_csv_cols(path)
    out = {}
    for r in rows:
        d = dt.date.fromisoformat(r["date"])
        out[d] = {k: fnum(v) for k, v in r.items() if k != "date"}
    return out, fields


def complete_years(series_list):
    """Anos civis com todos os dias presentes em todas as séries dadas."""
    yrs = sorted({d.year for d in series_list[0]})
    ok = []
    for y in yrs:
        d, good = dt.date(y, 1, 1), True
        while d.year == y:
            for s in series_list:
                if s.get(d) is None:
                    good = False
                    break
            if not good:
                break
            d += dt.timedelta(days=1)
        if good:
            ok.append(y)
    return ok


def year_matrix(years, value_fn):
    """S[y][i], N[y][i] (listas por ano) para um desfecho 0/1 ou None."""
    S, N = [], []
    for y in years:
        s, n = [0.0] * NCAL, [0.0] * NCAL
        d = dt.date(y, 1, 1)
        while d.year == y:
            v = value_fn(d)
            if v is not None:
                i = cal_index(d.month, d.day)
                n[i] += 1
                s[i] += v
            d += dt.timedelta(days=1)
        S.append(s)
        N.append(n)
    return S, N


# ------------------------------------------------------------ logística IRLS
def design(kmax=K_MAX):
    X = []
    for i in range(NCAL):
        t = 2 * math.pi * (i + 0.5) / NCAL
        row = [1.0]
        for k in range(1, kmax + 1):
            row += [math.cos(k * t), math.sin(k * t)]
        X.append(row)
    return X


XFULL = design()


def solve_spd(A, b):
    """Cholesky para matriz simétrica positiva definida."""
    n = len(b)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = A[i][j] - sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                if s <= 0:
                    s = 1e-12
                L[i][i] = math.sqrt(s)
            else:
                L[i][j] = s / L[j][j]
    y = [0.0] * n
    for i in range(n):
        y[i] = (b[i] - sum(L[i][k] * y[k] for k in range(i))) / L[i][i]
    x = [0.0] * n
    for i in reversed(range(n)):
        x[i] = (y[i] - sum(L[k][i] * x[k] for k in range(i + 1, n))) / L[i][i]
    return x


def sigmoid(e):
    if e >= 0:
        return 1.0 / (1.0 + math.exp(-e))
    z = math.exp(e)
    return z / (1.0 + z)


def fit_logit(succ, trials, K, beta0=None, tol=1e-10, maxit=60):
    """Newton-Raphson (= IRLS) para binomial agregada; devolve (beta, loglik)."""
    p = 2 * K + 1
    rows = [(XFULL[i][:p], succ[i], trials[i]) for i in range(NCAL) if trials[i] > 0]
    if beta0 is None:
        ts, tn = sum(r[1] for r in rows), sum(r[2] for r in rows)
        pm = min(max(ts / tn, 1e-6), 1 - 1e-6)
        beta = [math.log(pm / (1 - pm))] + [0.0] * (p - 1)
    else:
        beta = list(beta0[:p]) + [0.0] * max(0, p - len(beta0))
    for _ in range(maxit):
        g = [0.0] * p
        H = [[0.0] * p for _ in range(p)]
        for x, s, n in rows:
            mu = sigmoid(sum(a * b for a, b in zip(x, beta)))
            r = s - n * mu
            w = n * mu * (1 - mu)
            for a in range(p):
                xa = x[a]
                g[a] += xa * r
                wa = w * xa
                Ha = H[a]
                for b in range(a + 1):
                    Ha[b] += wa * x[b]
        for a in range(p):
            for b in range(a):
                H[b][a] = H[a][b]
        step = solve_spd(H, g)
        beta = [b + s for b, s in zip(beta, step)]
        if max(abs(s) for s in step) < tol:
            break
    ll = 0.0
    for x, s, n in rows:
        mu = min(max(sigmoid(sum(a * b for a, b in zip(x, beta))), 1e-12), 1 - 1e-12)
        ll += s * math.log(mu) + (n - s) * math.log(1 - mu)
    return beta, ll


def predict(beta):
    p = len(beta)
    return [sigmoid(sum(a * b for a, b in zip(XFULL[i][:p], beta))) for i in range(NCAL)]


def dec_means(pday):
    return [sum(pday[i] for i in d["idx"]) / len(d["idx"]) for d in DECS]


def aggregate(S, N, weights):
    s, n = [0.0] * NCAL, [0.0] * NCAL
    for w, sy, ny in zip(weights, S, N):
        if w:
            for i in range(NCAL):
                if ny[i]:
                    s[i] += w * sy[i]
                    n[i] += w * ny[i]
    return s, n


def dec_raw(s, n):
    out = []
    for d in DECS:
        ss = sum(s[i] for i in d["idx"])
        nn = sum(n[i] for i in d["idx"])
        out.append(ss / nn if nn else None)
    return out


# ------------------------------------------------------------- estatísticas
def wilson(k, n, z=Z90):
    if n == 0:
        return None, None
    ph = k / n
    den = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / den
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return c - h, c + h


def quantile(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    pos = (len(xs) - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def ranks(vals, best="min"):
    order = sorted(range(len(vals)), key=lambda j: vals[j], reverse=(best == "max"))
    r = [0] * len(vals)
    for pos, j in enumerate(order):
        r[j] = pos + 1
    return r


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = math.sqrt(sum((x - ma) ** 2 for x in ra))
    vb = math.sqrt(sum((y - mb) ** 2 for y in rb))
    return cov / (va * vb)


def rnd(x, nd=4):
    if x is None:
        return None
    return round(x, nd)


# ----------------------------------------------------- seleção de K (LOYO CV)
def select_k(S, N, kmax=K_MAX):
    ny = len(S)
    tot_s = [sum(S[y][i] for y in range(ny)) for i in range(NCAL)]
    tot_n = [sum(N[y][i] for y in range(ny)) for i in range(NCAL)]
    nobs = sum(tot_n)
    table = []
    betas_full = {}
    for K in range(0, kmax + 1):
        beta, ll = fit_logit(tot_s, tot_n, K, betas_full.get(K - 1))
        betas_full[K] = beta
        aic = -2 * ll + 2 * (2 * K + 1)
        bic = -2 * ll + math.log(nobs) * (2 * K + 1)
        loss, cnt, per_year = 0.0, 0, []
        cal_p = [0.0] * len(DECS)
        cal_n = [0.0] * len(DECS)
        for y in range(ny):
            s = [tot_s[i] - S[y][i] for i in range(NCAL)]
            n = [tot_n[i] - N[y][i] for i in range(NCAL)]
            b, _ = fit_logit(s, n, K, beta)
            pd = predict(b)
            ly, cy = 0.0, 0
            for i in SEASON_IDX:
                if N[y][i]:
                    pi = min(max(pd[i], 1e-12), 1 - 1e-12)
                    ly -= S[y][i] * math.log(pi) + (N[y][i] - S[y][i]) * math.log(1 - pi)
                    cy += N[y][i]
            loss += ly
            cnt += cy
            per_year.append(ly / cy if cy else 0.0)
            for j, d in enumerate(DECS):
                for i in d["idx"]:
                    if N[y][i]:
                        cal_p[j] += pd[i] * N[y][i]
                        cal_n[j] += N[y][i]
        m_py = sum(per_year) / ny
        se_py = math.sqrt(sum((x - m_py) ** 2 for x in per_year) / (ny - 1) / ny) if ny > 1 else 0.0
        table.append({"K": K, "n_params": 2 * K + 1, "loglik": ll, "aic": aic,
                      "bic": bic, "cv_logloss": loss / cnt, "cv_logloss_se": se_py,
                      "_per_year": per_year,
                      "_cal": [a / b if b else None for a, b in zip(cal_p, cal_n)]})
    # Referência: proporção bruta do decêndio (21 parâmetros na estação).
    loss, cnt = 0.0, 0
    for y in range(ny):
        for d in DECS:
            ss = sum(tot_s[i] - S[y][i] for i in d["idx"])
            nn = sum(tot_n[i] - N[y][i] for i in d["idx"])
            pi = min(max(ss / nn, 1e-12), 1 - 1e-12)
            for i in d["idx"]:
                if N[y][i]:
                    loss -= S[y][i] * math.log(pi) + (N[y][i] - S[y][i]) * math.log(1 - pi)
                    cnt += N[y][i]
    raw_cv = loss / cnt
    best = min(table, key=lambda r: r["cv_logloss"])
    # Regra de 1 erro-padrão (julgamento): o menor K cuja perda CV fica a até
    # 1 EP (entre anos) da melhor; evita perseguir ruído com pares a mais.
    py_best = best["_per_year"]
    for r in table:
        diffs = [a - b for a, b in zip(r["_per_year"], py_best)]
        m = sum(diffs) / ny
        sd = math.sqrt(sum((x - m) ** 2 for x in diffs) / (ny - 1)) if ny > 1 else 0
        r["cv_diff_vs_best"] = m
        r["cv_diff_se"] = sd / math.sqrt(ny)
    chosen = next(r for r in table if r["cv_diff_vs_best"] <= r["cv_diff_se"])
    cal = {r["K"]: r["_cal"] for r in table}
    for r in table:
        del r["_per_year"]
        del r["_cal"]
    return chosen["K"], best["K"], table, raw_cv, cal


# --------------------------------------------------------------- bootstrap
def boot_years(n_years, B, seed):
    rng = random.Random(seed)
    out = []
    for _ in range(B):
        w = [0] * n_years
        for _ in range(n_years):
            w[rng.randrange(n_years)] += 1
        out.append(w)
    return out


def analyse_outcome(name, S, N, years, best, weights_list, K=None, mm=None,
                    with_select=True):
    """Análise completa de um desfecho. best = 'min' (chuva) ou 'max' (aberto)."""
    ny = len(years)
    res = {"outcome": name, "best_is": "lowest" if best == "min" else "highest"}
    if with_select:
        K_sel, K_min, table, raw_cv, cal_loyo = select_k(S, N)
        res["model_selection"] = {
            "criterion": "leave-one-year-out log-loss on Apr–Oct days, "
                         "smallest K within 1 SE of the minimum",
            "K_chosen": K_sel, "K_min_cv": K_min,
            "K_min_aic": min(table, key=lambda r: r["aic"])["K"],
            "K_min_bic": min(table, key=lambda r: r["bic"])["K"],
            "table": [{k: (rnd(v, 6) if isinstance(v, float) else v)
                       for k, v in r.items()} for r in table],
            "raw_decendio_cv_logloss": rnd(raw_cv, 6),
        }
        K = K_sel
    else:
        cal_loyo = None
    ones = [1] * ny
    s, n = aggregate(S, N, ones)
    beta, _ = fit_logit(s, n, K)
    pday = predict(beta)
    p_model = dec_means(pday)
    p_raw = dec_raw(s, n)
    nd = len(DECS)

    # Bootstrap por anos.
    bm, br = [], []
    cnt_best = [0] * nd
    cnt_top3 = [0] * nd
    cnt_best_raw = [0] * nd
    cnt_top3_raw = [0] * nd
    # Empates nas proporções brutas (mesmo n, mesma contagem) são desfeitos
    # ao acaso com semente fixa, para não favorecer o decêndio de índice menor.
    rng_tie = random.Random(SEED + 7)
    rk_m, rk_r = [], []
    for w in weights_list:
        sb, nb = aggregate(S, N, w)
        b, _ = fit_logit(sb, nb, K, beta)
        pm = dec_means(predict(b))
        pr = dec_raw(sb, nb)
        bm.append(pm)
        br.append(pr)
        rm = ranks(pm, best)
        tb = [rng_tie.random() for _ in range(nd)]
        order_r = sorted(range(nd), key=lambda j: ((pr[j] if best == "min" else -pr[j]), tb[j]))
        rr = [0] * nd
        for pos, j in enumerate(order_r):
            rr[j] = pos + 1
        rk_m.append(rm)
        rk_r.append(rr)
        for j in range(nd):
            if rm[j] == 1:
                cnt_best[j] += 1
            if rm[j] <= 3:
                cnt_top3[j] += 1
            if rr[j] == 1:
                cnt_best_raw[j] += 1
            if rr[j] <= 3:
                cnt_top3_raw[j] += 1
    B = len(weights_list)
    r_point = ranks(p_model, best)
    jbest = r_point.index(1)

    per_year = []  # participação de cada ano em cada decêndio
    for d in DECS:
        vals = []
        for y in range(ny):
            ss = sum(S[y][i] for i in d["idx"])
            nn = sum(N[y][i] for i in d["idx"])
            vals.append(ss / nn if nn else None)
        per_year.append(vals)

    decs = []
    for j, d in enumerate(DECS):
        k = sum(s[i] for i in d["idx"])
        nn = sum(n[i] for i in d["idx"])
        lo, hi = wilson(k, nn)
        col_m = [b[j] for b in bm]
        col_r = [b[j] for b in br]
        diff = [b[j] - b[jbest] for b in bm]
        yv = [v for v in per_year[j] if v is not None]
        ndays = len(d["idx"])
        e = {
            "key": d["key"], "label": d["label"], "n_days_window": ndays,
            "n_obs": int(nn), "n_years": sum(1 for v in per_year[j] if v is not None),
            "count": int(k),
            "p_raw": rnd(k / nn), "p_raw_wilson90": [rnd(lo), rnd(hi)],
            "p_raw_boot90": [rnd(quantile(col_r, .05)), rnd(quantile(col_r, .95))],
            "p_model": rnd(p_model[j]),
            "p_model_boot90": [rnd(quantile(col_m, .05)), rnd(quantile(col_m, .95))],
            "rank_model": r_point[j],
            "P_best": rnd(cnt_best[j] / B), "P_top3": rnd(cnt_top3[j] / B),
            "P_best_raw": rnd(cnt_best_raw[j] / B), "P_top3_raw": rnd(cnt_top3_raw[j] / B),
            "diff_vs_best": rnd(p_model[j] - p_model[jbest]),
            "diff_vs_best_boot90": [rnd(quantile(diff, .05)), rnd(quantile(diff, .95))],
            "expected_days": rnd(p_model[j] * ndays, 2),
            "expected_days_boot90": [rnd(quantile(col_m, .05) * ndays, 2),
                                     rnd(quantile(col_m, .95) * ndays, 2)],
            "year_share_quartiles": [rnd(quantile(yv, q)) for q in (0, .25, .5, .75, 1)],
            "year_share_by_year": [rnd(v, 3) for v in per_year[j]],
        }
        decs.append(e)
    # Diferença bruta pareada (sem forma imposta) para o melhor do modelo:
    # o modelo harmônico com K pequeno fixa a forma da curva e por isso torna
    # artificialmente "significativas" diferenças de 0,2 p.p. entre vizinhos.
    # "Dentro do ruído" usa a versão bruta (julgamento; ver docs).
    for j, e in enumerate(decs):
        rd = [b[j] - b[jbest] for b in br]
        e["raw_diff_vs_best"] = rnd(p_raw[j] - p_raw[jbest])
        e["raw_diff_vs_best_boot90"] = [rnd(quantile(rd, .05)), rnd(quantile(rd, .95))]
    # "Dentro do ruído": não se pode mostrar que é pior que o melhor do modelo
    # (para mínimo: limite inferior da diferença <= 0; para máximo: superior >= 0).
    if best == "min":
        tied = [e["key"] for e in decs if e["key"] != DECS[jbest]["key"]
                and e["raw_diff_vs_best_boot90"][0] <= 0]
    else:
        tied = [e["key"] for e in decs if e["key"] != DECS[jbest]["key"]
                and e["raw_diff_vs_best_boot90"][1] >= 0]
    tied_model = [e["key"] for e in decs if e["key"] != DECS[jbest]["key"]
                  and e["diff_vs_best_boot90"][0] <= 0 <= e["diff_vs_best_boot90"][1]]

    def cover80(cnt):
        order = sorted(range(nd), key=lambda j: (-cnt[j], j))
        cum, cover = 0, []
        for j in order:
            cum += cnt[j]
            cover.append(DECS[j]["key"])
            if cum / B >= 0.8:
                break
        return cover, order[0]
    cover, jmodal = cover80(cnt_best)
    cover_raw, jmodal_raw = cover80(cnt_best_raw)
    # Sensibilidade do P(melhor) à ordem harmônica (mesmas réplicas).
    by_k = {}
    for Ka in range(1, 5):
        s0b, _ = fit_logit(s, n, Ka)
        cnt = [0] * nd
        for w in weights_list:
            sb, nb = aggregate(S, N, w)
            b, _ = fit_logit(sb, nb, Ka, s0b)
            cnt[ranks(dec_means(predict(b)), best).index(1)] += 1
        by_k["K%d" % Ka] = {DECS[j]["key"]: rnd(c / B) for j, c in enumerate(cnt) if c}
    res["P_best_by_K"] = by_k

    # ---- distribuição de postos (1 = melhor) por decêndio
    def rank_summary(rk):
        dist = [[0] * nd for _ in range(nd)]
        for r in rk:
            for j in range(nd):
                dist[j][r[j] - 1] += 1
        out = []
        for j in range(nd):
            col = [r[j] for r in rk]
            out.append({"p_rank": [rnd(c / B, 3) for c in dist[j]],
                        "median": quantile(col, .5),
                        "ci90": [quantile(col, .05), quantile(col, .95)]})
        return out
    rs_m, rs_r = rank_summary(rk_m), rank_summary(rk_r)
    for j, e in enumerate(decs):
        e["rank_raw_point"] = sorted(range(nd), key=lambda i: (p_raw[i] if best == "min" else -p_raw[i], i)).index(j) + 1
        e["rank_dist_model"] = rs_m[j]["p_rank"]
        e["rank_dist_raw"] = rs_r[j]["p_rank"]
        e["rank_median_model"] = rs_m[j]["median"]
        e["rank_ci90_model"] = rs_m[j]["ci90"]
        e["rank_median_raw"] = rs_r[j]["median"]
        e["rank_ci90_raw"] = rs_r[j]["ci90"]

    # ---- comparação par a par (linha i contra coluna j)
    sgn = 1 if best == "min" else -1

    def p_better(samples, i, j):
        c = 0.0
        for b in samples:
            a, z = sgn * b[i], sgn * b[j]
            c += 1.0 if a < z else (0.5 if a == z else 0.0)
        return c / B
    pw = {"P_better_raw": [], "P_better_model": [], "diff_raw": [], "diff_raw_ci90": [],
          "ci_excludes_zero": []}
    for i in range(nd):
        r1, r2, r3, r4, r5 = [], [], [], [], []
        for j in range(nd):
            if i == j:
                r1.append(None); r2.append(None); r3.append(0.0); r4.append([0.0, 0.0]); r5.append(False)
                continue
            r1.append(rnd(p_better(br, i, j), 3))
            r2.append(rnd(p_better(bm, i, j), 3))
            dd = [b[i] - b[j] for b in br]
            lo, hi = quantile(dd, .05), quantile(dd, .95)
            r3.append(rnd(p_raw[i] - p_raw[j]))
            r4.append([rnd(lo), rnd(hi)])
            r5.append(lo > 0 or hi < 0)
        pw["P_better_raw"].append(r1); pw["P_better_model"].append(r2)
        pw["diff_raw"].append(r3); pw["diff_raw_ci90"].append(r4); pw["ci_excludes_zero"].append(r5)
    res["pairwise"] = pw

    # ---- grupos (tiers): indistinguível do melhor / meio / indistinguível do pior
    jworst = r_point.index(nd)
    for j, e in enumerate(decs):
        rd = [b[j] - b[jworst] for b in br]
        e["raw_diff_vs_worst"] = rnd(p_raw[j] - p_raw[jworst])
        e["raw_diff_vs_worst_boot90"] = [rnd(quantile(rd, .05)), rnd(quantile(rd, .95))]
    if best == "min":
        near_worst = {e["key"] for e in decs if e["raw_diff_vs_worst_boot90"][1] >= 0}
    else:
        near_worst = {e["key"] for e in decs if e["raw_diff_vs_worst_boot90"][0] <= 0}
    near_best = set(tied) | {DECS[jbest]["key"]}
    near_worst |= {DECS[jworst]["key"]}
    for e in decs:
        kb, kw = e["key"] in near_best, e["key"] in near_worst
        e["tier"] = 2 if (kb and kw) else (1 if kb else (3 if kw else 2))
        e["tier_ambiguous"] = kb and kw
    res["worst_point"] = DECS[jworst]["key"]
    res["tiers_rule"] = ("1 = melhor do modelo ou sem diferença bruta pareada distinguível dele "
                         "(IC 90% bootstrap de anos não exclui que seja tão bom); "
                         "3 = pior do modelo ou sem diferença distinguível dele; 2 = demais "
                         "(e os que caem nos dois grupos, marcados tier_ambiguous)")
    res["calibration"] = {
        "pred_in_sample": [rnd(v) for v in p_model],
        "pred_loyo": [rnd(v) for v in cal_loyo[K]] if cal_loyo else None,
        "obs": [rnd(v) for v in p_raw],
        "obs_boot90": [decs[j]["p_raw_boot90"] for j in range(nd)],
    }
    res.update({
        "K": K, "beta": [rnd(b, 6) for b in beta],
        "best_point": DECS[jbest]["key"],
        "best_modal": DECS[jmodal]["key"],
        "best_modal_raw": DECS[jmodal_raw]["key"],
        "top3_point": [DECS[j]["key"] for j in sorted(range(nd), key=lambda j: r_point[j])[:3]],
        "set_covering_80pct_P_best": cover,
        "set_covering_80pct_P_best_raw": cover_raw,
        "within_noise_of_best": tied,
        "within_noise_of_best_model": tied_model,
        "daily_curve": [rnd(pday[i]) for i in SEASON_IDX],
        "decendios": decs,
    })
    return res


# Limiares de "período bom num ano" (julgamento; documentado em docs/modelo_periodos.md):
# contagens absolutas no decêndio (10 ou 11 dias).
GOOD_RULES = {
    "rain": [("le", 2, "até 2 dias chuvosos"), ("le", 0, "nenhum dia chuvoso")],
    "rain_ge5mm": [("le", 1, "até 1 dia com ≥ 5 mm"), ("le", 0, "nenhum dia com ≥ 5 mm")],
    "open": [("ge", 5, "5 ou mais dias abertos"), ("ge", 7, "7 ou mais dias abertos")],
    "bom": [("ge", 5, "5 ou mais dias bons"), ("ge", 7, "7 ou mais dias bons")],
}


def per_year_block(key, years_c, fn, partial_year):
    """Contagens por ano × decêndio (anos completos + ano parcial, marcado) e
    fração de anos em que o decêndio foi "bom" segundo GOOD_RULES."""
    ys = list(years_c) + ([partial_year] if partial_year else [])
    S, N = year_matrix(ys, fn)
    cnt = [[int(sum(S[y][i] for i in d["idx"])) for d in DECS] for y in range(len(ys))]
    nn = [[int(sum(N[y][i] for i in d["idx"])) for d in DECS] for y in range(len(ys))]
    good = []
    nc = len(years_c)
    for op, k, label in GOOD_RULES[key]:
        share, ci = [], []
        for j, d in enumerate(DECS):
            ok = [cnt[y][j] for y in range(nc) if nn[y][j] == len(d["idx"])]
            g = sum(1 for c in ok if (c <= k if op == "le" else c >= k))
            share.append(rnd(g / len(ok)) if ok else None)
            lo, hi = wilson(g, len(ok))
            ci.append([rnd(lo), rnd(hi)])
        good.append({"op": op, "k": k, "label": label, "share_years": share, "wilson90": ci})
    return {"years": ys, "partial_year": partial_year, "count": cnt, "n": nn,
            "n_days_window": [len(d["idx"]) for d in DECS], "good": good,
            "good_note": "fração dos anos completos em que o decêndio atingiu o critério; "
                         "IC de Wilson 90% tratando anos como independentes"}


def quick_rank(S, N, K, best):
    """Ajuste pontual (sem bootstrap) para checagens de robustez."""
    s, n = aggregate(S, N, [1] * len(S))
    beta, _ = fit_logit(s, n, K)
    pm = dec_means(predict(beta))
    pr = dec_raw(s, n)
    return pm, pr


def summarize_rank(pm, best):
    r = ranks(pm, best)
    order = sorted(range(len(pm)), key=lambda j: r[j])
    return {"top3": [DECS[j]["key"] for j in order[:3]],
            "p_model": [rnd(v) for v in pm]}


def ghcn_check():
    """Proporção de dias >= 1 mm por decêndio no Galeão (GHCN, cobertura falha)."""
    if not os.path.exists(GHCN):
        return None
    s, n = [0] * len(DECS), [0] * len(DECS)
    lookup = {}
    for j, d in enumerate(DECS):
        for day in range(d["day_from"], d["day_to"] + 1):
            lookup[(d["month"], day)] = j
    with open(GHCN, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["PRCP"].strip() == "":
                continue
            dd = dt.date.fromisoformat(r["DATE"])
            j = lookup.get((dd.month, dd.day))
            if j is None:
                continue
            n[j] += 1
            s[j] += 1 if float(r["PRCP"]) >= 1.0 else 0
    return s, n


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot", type=int, default=N_BOOT)
    args = ap.parse_args()

    rain = load_rain()
    cloud, cloud_info = load_cloud()
    last_rain = max(d for d, v in rain.items() if v is not None)
    years = complete_years([rain])
    ny = len(years)
    W = boot_years(ny, args.boot, SEED)

    def rain_fn(thr):
        return lambda d: (None if rain.get(d) is None else (1 if rain[d] >= thr else 0))

    out = {"meta": {}, "outcomes": {}, "robustness": {}}
    S1, N1 = year_matrix(years, rain_fn(1.0))
    S5, N5 = year_matrix(years, rain_fn(5.0))
    Smm, Nmm = year_matrix(years, lambda d: rain.get(d))

    res_rain = analyse_outcome("rain_ge1mm", S1, N1, years, "min", W)
    res_rain5 = analyse_outcome("rain_ge5mm", S5, N5, years, "min", W)

    # Chuva média (mm/dia) por decêndio, com IC bootstrap por anos.
    smm, nmm = aggregate(Smm, Nmm, [1] * ny)
    mm_point = dec_raw(smm, nmm)
    mm_boot = [dec_raw(*aggregate(Smm, Nmm, w)) for w in W]
    for j, e in enumerate(res_rain["decendios"]):
        nd = e["n_days_window"]
        col = [b[j] for b in mm_boot]
        e["mean_mm_day"] = rnd(mm_point[j], 3)
        e["mean_mm_window"] = rnd(mm_point[j] * nd, 1)
        e["mean_mm_window_boot90"] = [rnd(quantile(col, .05) * nd, 1),
                                      rnd(quantile(col, .95) * nd, 1)]
    out["outcomes"]["rain"] = res_rain
    out["outcomes"]["rain_ge5mm"] = res_rain5
    partial = last_rain.year if last_rain.year not in years else None
    res_rain["per_year"] = per_year_block("rain", years, rain_fn(1.0), partial)
    res_rain5["per_year"] = per_year_block("rain_ge5mm", years, rain_fn(5.0), partial)

    # Persistência (justifica o bootstrap por anos): P(chuva | ontem chuva)
    # vs P(chuva | ontem seco), dias abr–out; e fator de inflação da variância
    # das contagens anuais por decêndio frente à binomial.
    def persistence(S, N):
        a = b = c = e = 0
        for y in years:
            d = dt.date(y, 4, 2)
            while d <= dt.date(y, 10, 31):
                v, vp = rain_fn(1.0)(d), rain_fn(1.0)(d - dt.timedelta(days=1))
                if vp == 1:
                    a += v
                    b += 1
                else:
                    c += v
                    e += 1
                d += dt.timedelta(days=1)
        infl = []
        for d in DECS:
            ks = [sum(S[y][i] for i in d["idx"]) for y in range(ny)]
            ns = [sum(N[y][i] for i in d["idx"]) for y in range(ny)]
            p = sum(ks) / sum(ns)
            m = sum(ks) / ny
            var = sum((k - m) ** 2 for k in ks) / (ny - 1)
            infl.append(var / (ns[0] * p * (1 - p)))
        return {"p_rain_after_rain": rnd(a / b), "p_rain_after_dry": rnd(c / e),
                "variance_inflation_median": rnd(quantile(infl, .5), 2),
                "variance_inflation_range": [rnd(min(infl), 2), rnd(max(infl), 2)]}
    out["meta"]["persistence_rain_ge1mm"] = persistence(S1, N1)

    # Robustez: subamostras e limiares.
    K1 = res_rain["K"]
    rob = {}
    for lab, ys in (("1995-%d" % SPLIT_YEAR, [y for y in years if y <= SPLIT_YEAR]),
                    ("%d-%d" % (SPLIT_YEAR + 1, years[-1]), [y for y in years if y > SPLIT_YEAR])):
        idx = [years.index(y) for y in ys]
        Ss, Ns = [S1[i] for i in idx], [N1[i] for i in idx]
        pm, pr = quick_rank(Ss, Ns, K1, "min")
        Wsub = boot_years(len(ys), args.boot, SEED + 1)
        cnt = [0] * len(DECS)
        s0, n0 = aggregate(Ss, Ns, [1] * len(ys))
        b0, _ = fit_logit(s0, n0, K1)
        for w in Wsub:
            sb, nb = aggregate(Ss, Ns, w)
            b, _ = fit_logit(sb, nb, K1, b0)
            cnt[ranks(dec_means(predict(b)), "min").index(1)] += 1
        r = summarize_rank(pm, "min")
        r["years"] = [ys[0], ys[-1]]
        r["top3_raw"] = summarize_rank(pr, "min")["top3"]
        r["P_best"] = {DECS[j]["key"]: rnd(c / args.boot) for j, c in enumerate(cnt) if c}
        r["spearman_vs_full_model"] = rnd(spearman(pm, [e["p_model"] for e in res_rain["decendios"]]), 3)
        rob["rain_split_" + lab] = r
    pm5 = [e["p_model"] for e in res_rain5["decendios"]]
    pm1 = [e["p_model"] for e in res_rain["decendios"]]
    rob["rain_threshold_5mm_vs_1mm"] = {
        "spearman_model": rnd(spearman(pm1, pm5), 3),
        "top3_1mm": res_rain["top3_point"], "top3_5mm": res_rain5["top3_point"]}
    # Mesmo K do 1 mm aplicado ao 5 mm (e vice-versa não necessário).
    pmK, _ = quick_rank(S5, N5, K1, "min")
    rob["rain_threshold_5mm_vs_1mm"]["top3_5mm_sameK"] = summarize_rank(pmK, "min")["top3"]
    for thr in (0.5, 2.0, 10.0):
        St, Nt = year_matrix(years, rain_fn(thr))
        pm, pr = quick_rank(St, Nt, K1, "min")
        r = summarize_rank(pm, "min")
        r["spearman_vs_1mm_model"] = rnd(spearman(pm, pm1), 3)
        rob["rain_threshold_%gmm" % thr] = r
    # Sensibilidade de K: ranking com K-1 e K+1.
    for Kalt in (K1 - 1, K1 + 1):
        if 1 <= Kalt <= K_MAX:
            pm, _ = quick_rank(S1, N1, Kalt, "min")
            r = summarize_rank(pm, "min")
            r["spearman_vs_chosen"] = rnd(spearman(pm, pm1), 3)
            rob["rain_K%d" % Kalt] = r
    g = ghcn_check()
    if g:
        gs, gn = g
        gp = [a / b if b else None for a, b in zip(gs, gn)]
        rob["ghcn_galeao_ge1mm"] = {
            "note": "Galeão (GHCN-Daily BRM00083746), cobertura ~29% dos dias, "
                    "lacunas não aleatórias possíveis; checagem de forma, não de nível.",
            "n_obs": gn, "p_raw": [rnd(v) for v in gp],
            "wilson90": [[rnd(x) for x in wilson(a, b)] for a, b in zip(gs, gn)],
            "top3": [DECS[j]["key"] for j in sorted(range(len(DECS)), key=lambda j: gp[j])[:3]],
            "spearman_vs_era5_raw": rnd(spearman(gp, [e["p_raw"] for e in res_rain["decendios"]]), 3),
            "spearman_vs_era5_model": rnd(spearman(gp, pm1), 3),
        }

    # ---------------------------------------------------------------- nuvem
    cloud_meta = {"available": cloud is not None}
    last_cloud = None
    if cloud is not None:
        fields = cloud_info
        daycol = next((c for c in fields if c and "day" in c and "cloud" in c), None)
        meancol = next((c for c in fields if c and c.startswith("cloud_cover_mean")), None)
        ccol = daycol or meancol
        cyears = [y for y in complete_years([rain, {d: (v.get(ccol) if v else None)
                                                    for d, v in cloud.items()}]) if y in years]
        last_cloud = max(d for d, v in cloud.items() if v.get(ccol) is not None)
        cloud_meta.update({"columns": fields, "cloud_column_used": ccol,
                           "years": [cyears[0], cyears[-1]], "n_years": len(cyears)})
        Wc = boot_years(len(cyears), args.boot, SEED + 2)

        def open_fn(thr, col=ccol):
            def f(d):
                v = cloud.get(d)
                if not v or v.get(col) is None:
                    return None
                return 1 if v[col] <= thr + 1e-9 else 0  # igual a common.open_flags
            return f

        def bom_fn(d):
            o, r = open_fn(OPEN_THR)(d), rain_fn(1.0)(d)
            return None if o is None or r is None else o * (1 - r)

        So, No = year_matrix(cyears, open_fn(OPEN_THR))
        out["outcomes"]["open"] = analyse_outcome("open_cloud_le%g" % OPEN_THR, So, No, cyears, "max", Wc)
        Sb, Nb = year_matrix(cyears, bom_fn)
        out["outcomes"]["bom"] = analyse_outcome("bom_open_and_lt1mm", Sb, Nb, cyears, "max", Wc)
        pc = partial if partial and partial > cyears[-1] else None
        out["outcomes"]["open"]["per_year"] = per_year_block("open", cyears, open_fn(OPEN_THR), pc)
        out["outcomes"]["bom"]["per_year"] = per_year_block("bom", cyears, bom_fn, pc)
        Ko = out["outcomes"]["open"]["K"]
        po = [e["p_model"] for e in out["outcomes"]["open"]["decendios"]]
        for thr in (25.0, 37.5, 50.0):
            if abs(thr - OPEN_THR) < 1e-9:
                continue
            St, Nt = year_matrix(cyears, open_fn(thr))
            pm, _ = quick_rank(St, Nt, Ko, "max")
            r = summarize_rank(pm, "max")
            r["share_days_apr_oct"] = rnd(sum(sum(St[y][i] for i in SEASON_IDX) for y in range(len(St)))
                                          / sum(sum(Nt[y][i] for i in SEASON_IDX) for y in range(len(Nt))))
            r["spearman_vs_main"] = rnd(spearman(pm, po), 3)
            rob["open_cloud_le%g" % thr] = r
        if daycol and meancol:
            St, Nt = year_matrix(cyears, open_fn(OPEN_THR, meancol))
            pm, _ = quick_rank(St, Nt, Ko, "max")
            r = summarize_rank(pm, "max")
            r["spearman_vs_main"] = rnd(spearman(pm, po), 3)
            rob["open_24h_cloud_mean_le%g" % OPEN_THR] = r
        sun = next((c for c in fields if c and c.startswith("sunshine")), None)
        dayl = next((c for c in fields if c and c.startswith("daylight")), None)
        if sun and dayl:
            def sfrac(d):
                v = cloud.get(d)
                if not v or v.get(sun) is None or not v.get(dayl):
                    return None
                return v[sun] / v[dayl]
            season_days = [d for y in cyears for d in
                           (dt.date(y, 4, 1) + dt.timedelta(days=k) for k in range(214))]
            fr = sorted(x for x in (sfrac(d) for d in season_days) if x is not None)
            share_open = sum(open_fn(OPEN_THR)(d) or 0 for d in season_days) / len(season_days)
            # Limiar 0,6 (pedido) e limiar que iguala a fração de dias "abertos"
            # (casamento por quantil; julgamento, porque 0,6 classifica ~80%
            # dos dias abr–out como abertos no ERA5).
            q_thr = quantile(fr, 1 - share_open)
            for lab, thr in (("0.6", 0.6), ("quantile_matched", q_thr)):
                def sun_fn(d, thr=thr):
                    x = sfrac(d)
                    return None if x is None else (1 if x >= thr else 0)
                St, Nt = year_matrix(cyears, sun_fn)
                pm, _ = quick_rank(St, Nt, Ko, "max")
                r = summarize_rank(pm, "max")
                r["threshold"] = rnd(thr)
                r["share_days_apr_oct"] = rnd(sum(1 for x in fr if x >= thr) / len(fr))
                r["spearman_vs_main"] = rnd(spearman(pm, po), 3)
                rob["open_sunshine_frac_" + lab] = r
        for lab, ys in (("1995-%d" % SPLIT_YEAR, [y for y in cyears if y <= SPLIT_YEAR]),
                        ("%d-%d" % (SPLIT_YEAR + 1, cyears[-1]), [y for y in cyears if y > SPLIT_YEAR])):
            if len(ys) < 5:
                continue
            idx = [cyears.index(y) for y in ys]
            pm, _ = quick_rank([So[i] for i in idx], [No[i] for i in idx], Ko, "max")
            r = summarize_rank(pm, "max")
            r["years"] = [ys[0], ys[-1]]
            r["spearman_vs_full_model"] = rnd(spearman(pm, po), 3)
            rob["open_split_" + lab] = r
    else:
        cloud_meta["reason"] = cloud_info
    out["robustness"] = rob

    # ---- diagnósticos organizados (para a página do modelo)
    diag = {}
    for key, o in out["outcomes"].items():
        ms = o["model_selection"]
        diag[key] = {
            "K_chosen": ms["K_chosen"], "K_min_cv": ms["K_min_cv"],
            "K_min_aic": ms["K_min_aic"], "K_min_bic": ms["K_min_bic"],
            "k_table": [{"K": r["K"], "n_params": r["n_params"], "cv_logloss": r["cv_logloss"],
                         "cv_logloss_se": r["cv_logloss_se"], "cv_diff_vs_min": r["cv_diff_vs_best"],
                         "cv_diff_se": r["cv_diff_se"], "aic": round(r["aic"], 1),
                         "bic": round(r["bic"], 1)} for r in ms["table"]],
            "raw_decendio_cv_logloss": ms["raw_decendio_cv_logloss"],
            "calibration": o["calibration"],
        }
    rows = []

    def addrow(group, label, outcome, r, sp_key):
        rows.append({"group": group, "label": label, "outcome": outcome,
                     "top3": r.get("top3") or r.get("top3_5mm"),
                     "spearman": r.get(sp_key), "share_days_apr_oct": r.get("share_days_apr_oct"),
                     "P_best": r.get("P_best")})
    for k, r in rob.items():
        if k.startswith("rain_split_"):
            addrow("split", "Chuva ≥ 1 mm, " + k[len("rain_split_"):].replace("-", "–"), "rain", r, "spearman_vs_full_model")
        elif k.startswith("open_split_"):
            addrow("split", "Céu aberto, " + k[len("open_split_"):].replace("-", "–"), "open", r, "spearman_vs_full_model")
        elif k == "rain_threshold_5mm_vs_1mm":
            rows.append({"group": "threshold", "label": "Chuva ≥ 5 mm (K próprio)", "outcome": "rain",
                         "top3": r["top3_5mm"], "spearman": r["spearman_model"],
                         "share_days_apr_oct": None, "P_best": None})
        elif k.startswith("rain_threshold_"):
            addrow("threshold", "Chuva ≥ " + k[len("rain_threshold_"):].replace("mm", " mm").replace(".", ","),
                   "rain", r, "spearman_vs_1mm_model")
        elif k.startswith("rain_K"):
            addrow("K", "Chuva ≥ 1 mm com K = " + k[len("rain_K"):], "rain", r, "spearman_vs_chosen")
        elif k.startswith("open_cloud_le"):
            addrow("threshold", "Nuvem diurna ≤ " + k[len("open_cloud_le"):].replace(".", ",") + "%", "open", r,
                   "spearman_vs_main")
        elif k.startswith("open_24h_cloud_mean_le"):
            addrow("cloud24h", "Média de 24 h ≤ " + k[len("open_24h_cloud_mean_le"):].replace(".", ",") + "%",
                   "open", r, "spearman_vs_main")
        elif k.startswith("open_sunshine_frac_"):
            lab = ("Insolação ≥ 0,6 do dia" if k.endswith("0.6")
                   else "Insolação ≥ %s (mesma fração de dias)" % str(r["threshold"]).replace(".", ","))
            addrow("sunshine", lab, "open", r, "spearman_vs_main")
        elif k == "ghcn_galeao_ge1mm":
            rows.append({"group": "obs", "label": "Galeão (GHCN), chuva ≥ 1 mm, proporção bruta", "outcome": "rain",
                         "top3": r["top3"], "spearman": r["spearman_vs_era5_raw"],
                         "share_days_apr_oct": None, "P_best": None})
    diag["robustness_rows"] = rows
    diag["robustness_note"] = ("spearman = correlação de postos dos 21 decêndios com o ajuste principal "
                               "do mesmo desfecho (Galeão: com a proporção bruta do ERA5)")
    out["meta"]["diagnostics"] = diag

    last = last_rain if last_cloud is None else max(last_rain, last_cloud)
    out["meta"].update({
        "generated_at": last.isoformat(),
        "last_rain_date": last_rain.isoformat(),
        "last_cloud_date": last_cloud.isoformat() if last_cloud else None,
        "source": "Open-Meteo Historical Weather API, modelo era5, célula -22.75/-43.25",
        "years_used_rain": [years[0], years[-1]], "n_years_rain": ny,
        "partial_year_excluded": partial,
        "cloud": cloud_meta,
        "open_column": cloud_meta.get("cloud_column_used"),
        "open_threshold_pct": OPEN_THR,
        "definitions": {
            "rain": "precip_mm >= 1.0 (dia chuvoso)",
            "rain_ge5mm": "precip_mm >= 5.0 (sensibilidade; ERA5 superestima chuva fraca)",
            "open": "cobertura média de nuvens diurna (09–17 h, coluna meta.open_column) <= meta.open_threshold_pct "
                    "(common.OPEN_THR = 30%: classe 'clear', 0 a 3/10 de céu coberto, "
                    "NOAA/NCEI Comparative Climatic Data)",
            "bom": "aberto e precip_mm < 1.0",
            "decendio": "dias 1–10, 11–20, 21–fim de cada mês, abril a outubro (21 períodos)",
        },
        "model": {
            "spec": "logit P(desfecho no dia t) = b0 + sum_k [a_k cos(2πk t/366) + b_k sin(2πk t/366)], "
                    "ajustada no ano inteiro (366 dias de calendário), Newton/IRLS; "
                    "p do decêndio = média das probabilidades diárias",
            "K_selection": "log-loss deixando um ano de fora nos dias abr–out; menor K a até 1 EP do mínimo",
            "uncertainty": "bootstrap em blocos de anos (reamostra anos inteiros com reposição), "
                           "IC percentil 90%",
            "n_boot": args.boot, "seed": SEED, "seed_split": SEED + 1, "seed_cloud": SEED + 2,
            "wilson_z": round(Z90, 6),
        },
        "fields": {
            "p_raw": "proporção agregada de dias com o desfecho",
            "p_raw_wilson90": "IC de Wilson 90% (supõe dias independentes: estreito demais)",
            "p_raw_boot90": "IC 90% da proporção bruta por bootstrap de anos",
            "p_model": "probabilidade média do modelo harmônico no decêndio",
            "P_best": "fração das réplicas em que o decêndio é o melhor (menor chuva / maior aberto)",
            "P_top3": "fração das réplicas em que está entre os 3 melhores",
            "diff_vs_best": "p_model menos p_model do melhor decêndio pontual (IC por bootstrap pareado)",
            "expected_days": "p_model × dias do decêndio",
            "daily_curve": "probabilidade diária do modelo de 1/abr a 31/out (214 valores)",
        },
        "decendio_keys": [d["key"] for d in DECS],
        "decendio_labels": [d["label"] for d in DECS],
    })
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write("\n")
    os.replace(tmp, OUT)
    for k, r in out["outcomes"].items():
        print("%-11s K=%d melhor=%s top3=%s 80%%=%s" % (
            k, r["K"], r["best_point"], r["top3_point"], r["set_covering_80pct_P_best"]))
    print("gravado:", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
