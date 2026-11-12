#!/usr/bin/env python3
"""Atualiza data/daily/*.csv a partir da Open-Meteo Historical Weather API.

Estratégia: download COMPLETO a cada execução (1995-01-01 até ontem), em blocos
de 10 anos, três modelos (era5, ecmwf_ifs, best_match). São ~9 requisições,
bem abaixo do limite gratuito, e baixar tudo permite comparar a série inteira
com o CSV atual e detectar revisões históricas (ver --recent-days/--tolerance).
Uma estratégia incremental economizaria requisições irrelevantes e perderia
essa checagem.

Nada é gravado se qualquer validação falhar (all-or-nothing). Só biblioteca
padrão. Fonte/licença: https://open-meteo.com/en/terms (CC BY 4.0).

Uso:
  python3 scripts/fetch_data.py                  # atualiza tudo
  python3 scripts/fetch_data.py --dry-run        # baixa e valida, não grava
  python3 scripts/fetch_data.py --model era5     # só um modelo (repetível)
  python3 scripts/fetch_data.py --allow-revisions  # aceita revisões grandes
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

    results, revisions = {}, {}
    try:
        for m in models:
            dates, vals, info = fetch_model(m, args, start, end, today)
            old = read_csv(data_dir / f"{m}.csv")
            revisions[m] = find_revisions(old, dates, vals, today, args.recent_days, args.tolerance)
            results[m] = (dates, vals, info, old)
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
    for m, (dates, vals, _i, _o) in results.items():
        write_atomic(data_dir / f"{m}.csv", to_csv_text(dates, vals))
    write_atomic(meta_path, json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    print(f"Gravado em {data_dir}.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
