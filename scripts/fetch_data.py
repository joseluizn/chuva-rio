#!/usr/bin/env python3
"""Atualiza data/daily/*.csv a partir da Open-Meteo Historical Weather API.

Estratégia: download COMPLETO a cada execução (1995-01-01 até ontem), em blocos
de 10 anos, três modelos (era5, ecmwf_ifs, best_match). São ~9 requisições,
bem abaixo do limite gratuito, e baixar tudo permite comparar a série inteira
com o CSV atual e detectar revisões históricas (ver --recent-days/--tolerance).
Uma estratégia incremental economizaria requisições irrelevantes e perderia
essa checagem.

Também baixa a nebulosidade do ERA5 (era5_cloud.csv): cloud_cover_mean, sunshine_duration e
daylight_duration diários, e o cloud_cover horário de que se tira a média diurna (09h-17h locais).
É a base do "dia de tempo aberto" (ver docs/ATUALIZACAO.md e common.py).

Nada é gravado se qualquer validação falhar (all-or-nothing). Só biblioteca
padrão. Fonte/licença: https://open-meteo.com/en/terms (CC BY 4.0).

Uso:
  python3 scripts/fetch_data.py                  # atualiza tudo
  python3 scripts/fetch_data.py --dry-run        # baixa e valida, não grava
  python3 scripts/fetch_data.py --model era5     # só um modelo (repetível)
  python3 scripts/fetch_data.py --allow-revisions  # aceita revisões grandes
  python3 scripts/fetch_data.py --skip-cloud     # não baixa a nebulosidade
  python3 scripts/fetch_data.py --model era5 --cloud   # --model sozinho não baixa nebulosidade
"""
import argparse
import csv
import json
import math
import os
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

API = "https://archive-api.open-meteo.com/v1/archive"
LATITUDE = -22.9068
LONGITUDE = -43.1729
START_DATE = "1995-01-01"
TIMEZONE = "America/Sao_Paulo"
MODELS = ["era5", "ecmwf_ifs", "best_match"]
TOLERANCE_MM = 0.2      # mudança máxima aceita em dias históricos
RECENT_DAYS = 60        # dias mais novos que isso podem ser revisados à vontade
MAX_LAG_DAYS = 15       # último valor não nulo não pode ficar mais atrás que isso
CHUNK_YEARS = 10
CLOUD_HOURLY_CHUNK_YEARS = 5      # blocos menores para a série horária (87 mil valores em 10 anos)
CLOUD_TOLERANCE_PCT = 2.0         # revisão máxima aceita em cloud_cover_mean de dias antigos
DAY_HOURS = range(9, 18)          # 09h..17h locais (9 valores) para a nebulosidade diurna
CLOUD_DOC = {
    "columns": {
        "cloud_cover_mean_pct": "média diária das 24 horas da cobertura total de nuvens, % (API: cloud_cover_mean)",
        "sunshine_min": "sunshine_duration/60, em minutos inteiros (WMO: irradiância direta normal > 120 W/m2)",
        "daylight_min": "daylight_duration/60, em minutos inteiros",
        "cloud_daytime_0917_pct": "média do cloud_cover horário das 09:00 às 17:00 locais (9 valores), 1 decimal",
    },
    "notes": {
        "nulls": "dias finais sem cloud_cover_mean (atraso do ERA5) ficam vazios; a nebulosidade diurna é "
                 "esvaziada nos mesmos dias, para alinhar com a série diária",
        "source": "mesma célula de grade da chuva ERA5; modelo/reanálise, não observação",
    },
}
CLOUD_COLUMNS = ["date", "cloud_cover_mean_pct", "sunshine_min", "daylight_min", "cloud_daytime_0917_pct"]
USER_AGENT = "chuva-rio-data-updater/1.0 (+https://github.com/joseluizn/chuva-rio)"
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "daily"


class ValidationError(Exception):
    """Resposta ou série inválida: nunca deve ser gravada."""


def build_url(lat, lon, start, end, model):
    q = [("latitude", lat), ("longitude", lon), ("start_date", start),
         ("end_date", end), ("daily", "precipitation_sum"),
         ("timezone", TIMEZONE), ("models", model)]
    return API + "?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)


def split_ranges(start, end, years=CHUNK_YEARS):
    out, s = [], start
    while s <= end:
        e = min(end, date(s.year + years - 1, 12, 31))
        out.append((s, e))
        s = e + timedelta(days=1)
    return out


def http_get_json(url, retries=5, backoff=2.0, timeout=60):
    """GET com retries (backoff exponencial) para rede, 429 e 5xx."""
    last = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                                   "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            if e.code != 429 and e.code < 500:
                raise ValidationError(f"HTTP {e.code} em {url}: {body}")
            last = f"HTTP {e.code} {body}"
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = repr(e)
        except json.JSONDecodeError as e:
            last = f"JSON ilegível: {e}"
        if attempt < retries:
            wait = backoff * (2 ** attempt)
            print(f"  tentativa {attempt + 1} falhou ({last}); nova em {wait:.0f}s",
                  file=sys.stderr)
            time.sleep(wait)
    raise ValidationError(f"falha após {retries + 1} tentativas em {url}: {last}")


def parse_payload(payload, url):
    """Valida a estrutura de uma resposta e devolve (datas, valores, info)."""
    if not isinstance(payload, dict):
        raise ValidationError(f"resposta não é um objeto JSON: {url}")
    if payload.get("error"):
        raise ValidationError(f"API retornou erro: {payload.get('reason')} ({url})")
    daily = payload.get("daily")
    if not isinstance(daily, dict) or "time" not in daily or "precipitation_sum" not in daily:
        raise ValidationError(f"resposta sem daily.time/precipitation_sum: {url}")
    times, vals = daily["time"], daily["precipitation_sum"]
    if not isinstance(times, list) or not isinstance(vals, list) or len(times) != len(vals):
        raise ValidationError(f"daily.time e precipitation_sum com tamanhos diferentes: {url}")
    unit = (payload.get("daily_units") or {}).get("precipitation_sum")
    if unit != "mm":
        raise ValidationError(f"unidade inesperada {unit!r} (esperado 'mm'): {url}")
    for v in vals:
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))):
            raise ValidationError(f"valor não numérico {v!r}: {url}")
    try:
        dates = [date.fromisoformat(t) for t in times]
    except (TypeError, ValueError) as e:
        raise ValidationError(f"data inválida na resposta ({e}): {url}")
    info = {"returned_latitude": payload.get("latitude"),
            "returned_longitude": payload.get("longitude"),
            "elevation_m": payload.get("elevation")}
    return dates, [None if v is None else float(v) for v in vals], info


def validate_series(model, dates, vals, start, end, today, max_lag=MAX_LAG_DAYS):
    n = (end - start).days + 1
    if len(dates) != n or dates[0] != start or dates[-1] != end:
        raise ValidationError(f"[{model}] esperados {n} dias de {start} a {end}; "
                              f"recebidos {len(dates)} ({dates[:1]}..{dates[-1:]})")
    if len(set(dates)) != len(dates):
        raise ValidationError(f"[{model}] datas duplicadas")
    for i, d in enumerate(dates):
        if d != start + timedelta(days=i):
            raise ValidationError(f"[{model}] datas não contínuas perto de {d}")
    for d, v in zip(dates, vals):
        if v is not None and (not math.isfinite(v) or v < 0):
            raise ValidationError(f"[{model}] valor inválido {v} em {d}")
    idx = [i for i, v in enumerate(vals) if v is not None]
    if not idx:
        raise ValidationError(f"[{model}] série inteira nula")
    first, last = idx[0], idx[-1]
    holes = [dates[i] for i in range(first, last) if vals[i] is None]
    if holes:
        raise ValidationError(f"[{model}] nulos no meio da série (só no início/fim são aceitos): "
                              f"{[str(h) for h in holes[:5]]}{'...' if len(holes) > 5 else ''}")
    lag = (end - dates[last]).days
    if lag > max_lag:
        raise ValidationError(f"[{model}] último valor em {dates[last]}, {lag} dias antes de "
                              f"{end} (máx. {max_lag}); a fonte pode estar atrasada")


def build_cloud_url(lat, lon, start, end, kind):
    var = ("daily", "cloud_cover_mean,sunshine_duration,daylight_duration") if kind == "daily" \
        else ("hourly", "cloud_cover")
    q = [("latitude", lat), ("longitude", lon), ("start_date", start), ("end_date", end),
         var, ("timezone", TIMEZONE), ("models", "era5")]
    return API + "?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)


def _num_list(block, key, url, unit_expect=None, units=None):
    vals = block.get(key)
    if not isinstance(vals, list) or len(vals) != len(block.get("time", [])):
        raise ValidationError(f"resposta sem {key} ou com tamanho diferente de time: {url}")
    if unit_expect is not None and (units or {}).get(key) != unit_expect:
        raise ValidationError(f"unidade inesperada {(units or {}).get(key)!r} em {key} "
                              f"(esperado {unit_expect!r}): {url}")
    for v in vals:
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))
                              or not math.isfinite(v)):
            raise ValidationError(f"valor inválido {v!r} em {key}: {url}")
    return vals


def parse_cloud_daily(payload, url):
    """-> (datas, cloud_mean %, sunshine_s, daylight_s, info)."""
    if not isinstance(payload, dict) or payload.get("error"):
        raise ValidationError(f"resposta inválida/erro da API: {url}")
    d = payload.get("daily")
    if not isinstance(d, dict) or "time" not in d:
        raise ValidationError(f"resposta sem daily.time: {url}")
    u = payload.get("daily_units") or {}
    cc = _num_list(d, "cloud_cover_mean", url, "%", u)
    sun = _num_list(d, "sunshine_duration", url, "s", u)
    day = _num_list(d, "daylight_duration", url, "s", u)
    try:
        dates = [date.fromisoformat(t) for t in d["time"]]
    except (TypeError, ValueError) as e:
        raise ValidationError(f"data inválida ({e}): {url}")
    info = {"returned_latitude": payload.get("latitude"), "returned_longitude": payload.get("longitude"),
            "elevation_m": payload.get("elevation")}
    return dates, cc, sun, day, info


def parse_cloud_hourly(payload, url):
    """-> {data: média das horas 09..17 locais (1 decimal) ou None} + info.
    Só vale dia com as 9 horas presentes e não nulas."""
    if not isinstance(payload, dict) or payload.get("error"):
        raise ValidationError(f"resposta inválida/erro da API: {url}")
    h = payload.get("hourly")
    if not isinstance(h, dict) or "time" not in h:
        raise ValidationError(f"resposta sem hourly.time: {url}")
    cc = _num_list(h, "cloud_cover", url, "%", payload.get("hourly_units"))
    by = {}
    for t, v in zip(h["time"], cc):
        try:
            hour = int(t[11:13])
            day = date.fromisoformat(t[:10])
        except (TypeError, ValueError):
            raise ValidationError(f"hora inválida {t!r}: {url}")
        if hour in DAY_HOURS:
            by.setdefault(day, []).append(v)
    out = {d: (round(sum(v) / len(v), 1) if len(v) == len(DAY_HOURS) and None not in v else None)
           for d, v in by.items()}
    info = {"returned_latitude": payload.get("latitude"), "returned_longitude": payload.get("longitude"),
            "elevation_m": payload.get("elevation")}
    return out, info


def validate_cloud(dates, cc, sun, day, dayt, start, end, today, max_lag=MAX_LAG_DAYS):
    """Mesmas regras da chuva + limites físicos. Nulos só no fim (cloud/sunshine) da série."""
    validate_series("cloud", dates, [None if v is None else float(v) for v in cc], start, end, today, max_lag)
    for i, d in enumerate(dates):
        for name, v, hi in (("cloud_cover_mean", cc[i], 100), ("cloud_daytime", dayt[i], 100)):
            if v is not None and not (0 <= v <= hi + 1e-9):
                raise ValidationError(f"[cloud] {name}={v} fora de 0..{hi} em {d}")
        if day[i] is None:
            raise ValidationError(f"[cloud] daylight_duration nulo em {d}")
        if not 0 < day[i] <= 24 * 60:
            raise ValidationError(f"[cloud] daylight_min={day[i]} implausível em {d}")
        if sun[i] is not None and not (0 <= sun[i] <= day[i] + 1):
            raise ValidationError(f"[cloud] sunshine_min={sun[i]} fora de 0..daylight ({day[i]}) em {d}")
        if (cc[i] is None) != (sun[i] is None):
            raise ValidationError(f"[cloud] nulos inconsistentes entre cloud_cover_mean e sunshine em {d}")


def cloud_to_csv_text(dates, cc, sun, day, dayt):
    f = lambda v, fmt="{}": "" if v is None else fmt.format(v)
    lines = [",".join(CLOUD_COLUMNS)]
    for i, d in enumerate(dates):
        lines.append(",".join([d.isoformat(), f(cc[i]), f(sun[i]), f(day[i]), f(dayt[i], "{:.1f}")]))
    return "\n".join(lines) + "\n"


def read_cloud_csv(path):
    if not Path(path).exists():
        return None
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        rd = csv.reader(f)
        next(rd, None)
        for row in rd:
            if len(row) >= 2 and row[0]:
                out[row[0]] = float(row[1]) if row[1] != "" else None
    return out


def fetch_cloud(args, start, end, today):
    """Baixa e valida a nebulosidade ERA5. Devolve (texto_csv, meta_cloud, dados p/ revisão)."""
    dates, cc, sun, day, info = [], [], [], [], None
    for s, e in split_ranges(start, end):
        url = build_cloud_url(args.lat, args.lon, s.isoformat(), e.isoformat(), "daily")
        print(f"  cloud diário: {s} .. {e}", file=sys.stderr)
        d, c, su, da, i = parse_cloud_daily(http_get_json(url, args.retries, args.backoff, args.timeout), url)
        if info is None:
            info = i
        elif i != info:
            raise ValidationError(f"[cloud] ponto de grade/elevação mudou entre blocos: {info} vs {i}")
        dates += d
        cc += c
        sun += su
        day += da
    hourly = {}
    for s, e in split_ranges(start, end, CLOUD_HOURLY_CHUNK_YEARS):
        url = build_cloud_url(args.lat, args.lon, s.isoformat(), e.isoformat(), "hourly")
        print(f"  cloud horário: {s} .. {e}", file=sys.stderr)
        h, i = parse_cloud_hourly(http_get_json(url, args.retries, args.backoff, args.timeout), url)
        if i != info:
            raise ValidationError(f"[cloud] grade do horário difere do diário: {info} vs {i}")
        hourly.update(h)
    sun_min = [None if v is None else round(v / 60) for v in sun]
    day_min = [None if v is None else round(v / 60) for v in day]
    # nebulosidade diurna: alinhada aos nulos do diário (a hora pode existir um dia a mais que o diário)
    dayt = [hourly.get(d) if cc[i] is not None else None for i, d in enumerate(dates)]
    validate_cloud(dates, cc, sun_min, day_min, dayt, start, end, today, args.max_lag)
    nd = sum(1 for i in range(len(dates)) if cc[i] is not None and dayt[i] is None)
    if nd:
        raise ValidationError(f"[cloud] {nd} dias com cloud_cover_mean mas sem as 9 horas diurnas")
    old = read_cloud_csv(Path(args.data_dir) / "era5_cloud.csv")
    revisions = find_revisions(old, dates, [None if v is None else float(v) for v in cc],
                               today, args.recent_days, CLOUD_TOLERANCE_PCT)
    nn = [d for d, v in zip(dates, cc) if v is not None]
    meta_cloud = {"accessed": today.isoformat(), "file": "era5_cloud.csv", "model": "era5",
                  "url": build_cloud_url(args.lat, args.lon, start.isoformat(), end.isoformat(), "daily"),
                  "hourly_url_pattern": build_cloud_url(args.lat, args.lon, "YYYY-01-01", "YYYY-12-31", "hourly"),
                  **info, "days": len(dates), "first_date": start.isoformat(),
                  "last_date_with_value": nn[-1].isoformat(), "null_days": len(dates) - len(nn)}
    return cloud_to_csv_text(dates, cc, sun_min, day_min, dayt), meta_cloud, info, revisions


def read_csv(path):
    if not Path(path).exists():
        return None
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        rd = csv.reader(f)
        next(rd, None)
        for row in rd:
            if len(row) >= 2 and row[0]:
                out[row[0]] = float(row[1]) if row[1] != "" else None
    return out


def to_csv_text(dates, vals):
    lines = ["date,precip_mm"]
    for d, v in zip(dates, vals):
        lines.append(f"{d.isoformat()},{'' if v is None else repr(v)}")
    return "\n".join(lines) + "\n"


def find_revisions(old, dates, vals, today, recent_days, tol):
    """Dias anteriores a today-recent_days cujo valor mudou mais que tol (ou sumiu)."""
    if not old:
        return []
    cutoff = today - timedelta(days=recent_days)
    out = []
    for d, v in zip(dates, vals):
        if d >= cutoff:
            continue
        o = old.get(d.isoformat())
        if o is None:
            continue
        if v is None or abs(v - o) > tol + 1e-9:
            out.append((d.isoformat(), o, v))
    return out


def count_changed(old, dates, vals):
    if not old:
        return 0
    return sum(1 for d, v in zip(dates, vals)
               if old.get(d.isoformat()) is not None and v is not None
               and abs(old[d.isoformat()] - v) > 1e-9)


def write_atomic(path, text):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def fetch_model(model, args, start, end, today):
    chunks = split_ranges(start, end)
    dates, vals, info = [], [], None
    for s, e in chunks:
        url = build_url(args.lat, args.lon, s.isoformat(), e.isoformat(), model)
        print(f"  {model}: {s} .. {e}", file=sys.stderr)
        d, v, i = parse_payload(http_get_json(url, args.retries, args.backoff, args.timeout), url)
        if info is None:
            info = i
        elif i != info:
            raise ValidationError(f"[{model}] ponto de grade/elevação mudou entre blocos: {info} vs {i}")
        dates += d
        vals += v
    validate_series(model, dates, vals, start, end, today, args.max_lag)
    return dates, vals, info


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--model", action="append", choices=MODELS,
                   help="modelo a atualizar (repetível; padrão: todos)")
    p.add_argument("--dry-run", action="store_true", help="baixa e valida, não grava nada")
    p.add_argument("--allow-revisions", action="store_true",
                   help="aceita revisões históricas acima da tolerância (inspecione o diff antes)")
    p.add_argument("--tolerance", type=float, default=TOLERANCE_MM, help="mm (padrão %(default)s)")
    p.add_argument("--recent-days", type=int, default=RECENT_DAYS,
                   help="dias recentes isentos da checagem de revisão (padrão %(default)s)")
    p.add_argument("--cloud", action="store_true",
                   help="baixa também a nebulosidade quando --model é usado (sem --model já baixa)")
    p.add_argument("--skip-cloud", action="store_true", help="não baixa a nebulosidade ERA5")
    p.add_argument("--lat", default=str(LATITUDE))
    p.add_argument("--lon", default=str(LONGITUDE))
    p.add_argument("--start-date", default=START_DATE)
    p.add_argument("--end-date", help="padrão: ontem (fuso de Brasília)")
    p.add_argument("--today", help="AAAA-MM-DD; só para testes/reprodução")
    p.add_argument("--data-dir", default=str(DATA_DIR))
    p.add_argument("--max-lag", type=int, default=MAX_LAG_DAYS)
    p.add_argument("--retries", type=int, default=5)
    p.add_argument("--backoff", type=float, default=2.0)
    p.add_argument("--timeout", type=int, default=60)
    args = p.parse_args(argv)

    today = (date.fromisoformat(args.today) if args.today
             else datetime.now(timezone(timedelta(hours=-3))).date())
    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date) if args.end_date else today - timedelta(days=1)
    models = args.model or MODELS
    data_dir = Path(args.data_dir)
    print(f"Open-Meteo: {start} .. {end}, modelos {models}", file=sys.stderr)

    do_cloud = args.cloud or (not args.model and not args.skip_cloud)
    results, revisions, cloud = {}, {}, None
    try:
        for m in models:
            dates, vals, info = fetch_model(m, args, start, end, today)
            old = read_csv(data_dir / f"{m}.csv")
            revisions[m] = find_revisions(old, dates, vals, today, args.recent_days, args.tolerance)
            results[m] = (dates, vals, info, old)
        if do_cloud:
            cloud = fetch_cloud(args, start, end, today)
            if "era5" in results and results["era5"][2] != cloud[2]:
                raise ValidationError(f"[cloud] célula de grade difere da série de chuva ERA5: "
                                      f"{cloud[2]} vs {results['era5'][2]}")
    except ValidationError as e:
        print(f"ERRO de validação: {e}\nNada foi gravado.", file=sys.stderr)
        return 1

    for m, (dates, vals, info, old) in results.items():
        nn = [d for d, v in zip(dates, vals) if v is not None]
        added = sum(1 for d, v in zip(dates, vals)
                    if v is not None and (old is None or old.get(d.isoformat()) is None))
        print(f"{m}: {len(dates)} dias, valores {nn[0]}..{nn[-1]}, "
              f"{len(dates) - len(nn)} nulos, dias novos/preenchidos {added}, "
              f"dias alterados {count_changed(old, dates, vals)}, "
              f"revisões acima da tolerância {len(revisions[m])}")

    if cloud is not None:
        revisions["cloud"] = cloud[3]
        print(f"cloud: {cloud[1]['days']} dias, valores até {cloud[1]['last_date_with_value']}, "
              f"{cloud[1]['null_days']} nulos, revisões acima da tolerância {len(cloud[3])}")
    bad = {m: r for m, r in revisions.items() if r}
    if bad and not args.allow_revisions:
        print(f"\nERRO: valores anteriores a {today - timedelta(days=args.recent_days)} mudaram "
              f"mais que {args.tolerance} mm. Nada foi gravado.", file=sys.stderr)
        for m, r in bad.items():
            print(f"  {m}: {len(r)} dias; maiores diferenças (data, atual, novo):", file=sys.stderr)
            for d, o, v in sorted(r, key=lambda x: -abs((x[2] or 0) - x[1]))[:10]:
                print(f"    {d}  {o}  ->  {v}", file=sys.stderr)
        print("Inspecione e, se a revisão for legítima, rode com --allow-revisions "
              "(ver docs/ATUALIZACAO.md).", file=sys.stderr)
        return 1

    if args.dry_run:
        print("--dry-run: nada gravado.", file=sys.stderr)
        return 0

    meta_path = data_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    meta["accessed"] = today.isoformat()
    meta["requested"] = {"latitude": float(args.lat), "longitude": float(args.lon),
                         "start_date": start.isoformat(), "end_date": end.isoformat(),
                         "timezone": TIMEZONE, "daily": "precipitation_sum"}
    meta["units"] = "mm"
    mm = meta.setdefault("models", {})
    for m, (dates, vals, info, _old) in results.items():
        nn = [d for d, v in zip(dates, vals) if v is not None]
        mm[m] = {"url": build_url(args.lat, args.lon, start.isoformat(), end.isoformat(), m),
                 **info, "days": len(dates),
                 "first_date_with_value": nn[0].isoformat(),
                 "last_date_with_value": nn[-1].isoformat(),
                 "null_days": len(dates) - len(nn)}
    if "era5" in results:
        d, v, _, _ = results["era5"]
        tail = [x.isoformat() for x, y in zip(d, v) if y is None and x > date.fromisoformat(
            mm["era5"]["last_date_with_value"])]
        meta.setdefault("notes", {})["era5_nulls"] = (
            f"era5 últimos {len(tail)} dias ({tail[0]}..{tail[-1]}) nulos (atraso da reanálise)"
            if tail else "era5 sem nulos finais")
    notes = meta.setdefault("notes", {})
    notes["updated_by"] = "scripts/fetch_data.py"
    for k in [k for k in notes if k.isdigit() and len(k) == 4]:   # nota de ano parcial
        del notes[k]
    if end < date(end.year, 12, 31):
        notes[str(end.year)] = f"partial year (through {end.isoformat()})"
    if cloud is not None:
        meta["cloud"] = {**CLOUD_DOC, **cloud[1]}
        meta["cloud"]["same_grid_cell_as_rain_era5"] = (
            "era5" not in results or results["era5"][2] == cloud[2])
        write_atomic(data_dir / "era5_cloud.csv", cloud[0])
    for m, (dates, vals, _i, _o) in results.items():
        write_atomic(data_dir / f"{m}.csv", to_csv_text(dates, vals))
    write_atomic(meta_path, json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    print(f"Gravado em {data_dir}.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
