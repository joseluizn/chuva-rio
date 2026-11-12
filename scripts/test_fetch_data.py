#!/usr/bin/env python3
"""Testes de scripts/fetch_data.py, sem rede (urllib é simulado).

Rodar: python3 -m unittest scripts/test_fetch_data.py -v
"""
import io
import json
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_data as fd  # noqa: E402

TODAY = "2024-04-01"
START, END = date(2024, 1, 1), date(2024, 3, 31)


def series(start=START, end=END, fn=lambda i: round((i % 7) * 1.3, 1)):
    d, i, out = start, 0, {}
    while d <= end:
        out[d.isoformat()] = fn(i)
        d += timedelta(days=1)
        i += 1
    return out


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def make_urlopen(data, **extra):
    """urlopen falso: responde com o recorte start_date..end_date de `data`."""
    def _open(req, timeout=None):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(req.full_url).query)
        s, e = date.fromisoformat(q["start_date"][0]), date.fromisoformat(q["end_date"][0])
        days = [(s + timedelta(days=i)).isoformat() for i in range((e - s).days + 1)]
        body = {"latitude": -22.75, "longitude": -43.25, "elevation": 12.0,
                "daily_units": {"time": "iso8601", "precipitation_sum": "mm"},
                "daily": {"time": days, "precipitation_sum": [data.get(d) for d in days]}}
        body.update(extra)
        return FakeResp(json.dumps(body).encode())
    return _open


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def write_old(self, data, model="era5"):
        (self.dir / f"{model}.csv").write_text(
            fd.to_csv_text([date.fromisoformat(k) for k in data], list(data.values())))

    def run_main(self, data, *extra, model="era5"):
        argv = ["--model", model, "--data-dir", str(self.dir), "--today", TODAY,
                "--start-date", START.isoformat(), "--end-date", END.isoformat(),
                "--backoff", "0", *extra]
        with mock.patch("fetch_data.urllib.request.urlopen", make_urlopen(data)), \
                mock.patch("fetch_data.time.sleep"):
            return fd.main(argv)


class TestNormal(Base):
    def test_normal_writes_csv_and_meta(self):
        data = series()
        old = {k: v for k, v in data.items() if k < "2024-03-20"}
        self.write_old(old)
        (self.dir / "meta.json").write_text(json.dumps({"models": {"era5_land": {"x": 1}}, "notes": {"a": "b"}}))
        self.assertEqual(self.run_main(data), 0)
        got = fd.read_csv(self.dir / "era5.csv")
        self.assertEqual(len(got), 91)
        self.assertEqual(got, data)
        meta = json.loads((self.dir / "meta.json").read_text())
        self.assertEqual(meta["accessed"], TODAY)
        self.assertEqual(meta["models"]["era5"]["last_date_with_value"], "2024-03-31")
        self.assertEqual(meta["models"]["era5"]["null_days"], 0)
        self.assertEqual(meta["models"]["era5"]["elevation_m"], 12.0)
        self.assertEqual(meta["models"]["era5"]["returned_latitude"], -22.75)
        self.assertIn("era5_land", meta["models"])       # preserva o que não foi tocado
        self.assertEqual(meta["notes"]["a"], "b")
        self.assertTrue(meta["models"]["era5"]["url"].startswith(fd.API))
        self.assertFalse(list(self.dir.glob("*.tmp")))

    def test_dry_run_writes_nothing(self):
        self.assertEqual(self.run_main(series(), "--dry-run"), 0)
        self.assertFalse((self.dir / "era5.csv").exists())

    def test_url_matches_existing_meta_format(self):
        self.assertEqual(
            fd.build_url("-22.9068", "-43.1729", "1995-01-01", "2026-11-11", "era5"),
            "https://archive-api.open-meteo.com/v1/archive?latitude=-22.9068&longitude=-43.1729"
            "&start_date=1995-01-01&end_date=2026-11-11&daily=precipitation_sum"
            "&timezone=America%2FSao_Paulo&models=era5")

    def test_split_ranges(self):
        r = fd.split_ranges(date(1995, 1, 1), date(2026, 11, 11))
        self.assertEqual(r[0], (date(1995, 1, 1), date(2004, 12, 31)))
        self.assertEqual(r[-1], (date(2025, 1, 1), date(2026, 11, 11)))
        self.assertEqual(len(r), 4)

    def test_multi_chunk_roundtrip(self):
        s, e = date(1995, 1, 1), date(2006, 6, 30)
        data = series(s, e)
        argv = ["--model", "era5", "--data-dir", str(self.dir), "--today", "2006-07-01",
                "--start-date", s.isoformat(), "--end-date", e.isoformat()]
        calls = []
        op = make_urlopen(data)
        with mock.patch("fetch_data.urllib.request.urlopen",
                        lambda req, timeout=None: (calls.append(1), op(req))[1]):
            self.assertEqual(fd.main(argv), 0)
        self.assertEqual(len(calls), 2)
        self.assertEqual(fd.read_csv(self.dir / "era5.csv"), data)


class TestNulls(Base):
    def test_trailing_nulls(self):
        data = series()
        for i in range(6):
            data[(END - timedelta(days=i)).isoformat()] = None
        self.assertEqual(self.run_main(data), 0)
        text = (self.dir / "era5.csv").read_text()
        self.assertTrue(text.endswith("2024-03-31,\n"))
        meta = json.loads((self.dir / "meta.json").read_text())
        self.assertEqual(meta["models"]["era5"]["last_date_with_value"], "2024-03-25")
        self.assertEqual(meta["models"]["era5"]["null_days"], 6)
        self.assertIn("6 dias", meta["notes"]["era5_nulls"])

    def test_leading_nulls_ok(self):
        data = series()
        for k in list(data)[:30]:
            data[k] = None
        self.assertEqual(self.run_main(data), 0)

    def test_interior_null_rejected(self):
        data = series()
        data["2024-02-10"] = None
        self.assertEqual(self.run_main(data), 1)
        self.assertFalse((self.dir / "era5.csv").exists())

    def test_excessive_lag_rejected(self):
        data = series()
        for i in range(20):
            data[(END - timedelta(days=i)).isoformat()] = None
        self.assertEqual(self.run_main(data), 1)


class TestRevisions(Base):
    def test_historical_revision_blocks(self):
        data = series()
        self.write_old(data)
        before = (self.dir / "era5.csv").read_text()
        data["2024-01-15"] += 5.0                      # > 60 dias antes de TODAY
        self.assertEqual(self.run_main(data), 1)
        self.assertEqual((self.dir / "era5.csv").read_text(), before)
        self.assertFalse((self.dir / "meta.json").exists())

    def test_historical_value_vanishing_blocks(self):
        data = series()
        self.write_old(data)
        data["2024-01-15"] = None
        self.assertEqual(self.run_main(data), 1)

    def test_allow_revisions(self):
        data = series()
        self.write_old(data)
        data["2024-01-15"] += 5.0
        self.assertEqual(self.run_main(data, "--allow-revisions"), 0)
        self.assertEqual(fd.read_csv(self.dir / "era5.csv")["2024-01-15"], data["2024-01-15"])

    def test_small_and_recent_revisions_ok(self):
        data = series()
        self.write_old(data)
        data["2024-01-15"] = round(data["2024-01-15"] + 0.1, 1)   # dentro da tolerância
        data["2024-03-25"] += 9.0                                 # recente (< 60 dias)
        self.assertEqual(self.run_main(data), 0)


class TestMalformed(Base):
    def check_rejected(self, mutate):
        data = series()
        op = make_urlopen(data)

        def _open(req, timeout=None):
            body = json.loads(op(req).read())
            return FakeResp(json.dumps(mutate(body)).encode())
        argv = ["--model", "era5", "--data-dir", str(self.dir), "--today", TODAY,
                "--start-date", START.isoformat(), "--end-date", END.isoformat(), "--backoff", "0"]
        with mock.patch("fetch_data.urllib.request.urlopen", _open), mock.patch("fetch_data.time.sleep"):
            self.assertEqual(fd.main(argv), 1)
        self.assertFalse((self.dir / "era5.csv").exists())

    def test_missing_daily(self):
        self.check_rejected(lambda b: {"latitude": 1})

    def test_error_payload(self):
        self.check_rejected(lambda b: {"error": True, "reason": "limite"})

    def test_length_mismatch(self):
        def m(b):
            b["daily"]["precipitation_sum"].pop()
            return b
        self.check_rejected(m)

    def test_negative_value(self):
        def m(b):
            b["daily"]["precipitation_sum"][5] = -1.0
            return b
        self.check_rejected(m)

    def test_duplicate_date(self):
        def m(b):
            b["daily"]["time"][10] = b["daily"]["time"][9]
            return b
        self.check_rejected(m)

    def test_gap_in_dates(self):
        def m(b):
            for k in ("time", "precipitation_sum"):
                del b["daily"][k][10]
            return b
        self.check_rejected(m)

    def test_wrong_unit(self):
        def m(b):
            b["daily_units"]["precipitation_sum"] = "inch"
            return b
        self.check_rejected(m)

    def test_string_value(self):
        def m(b):
            b["daily"]["precipitation_sum"][3] = "1.0"
            return b
        self.check_rejected(m)

    def test_all_models_or_nothing(self):
        """Se um modelo falha, nenhum CSV é gravado."""
        data = series()
        op = make_urlopen(data)

        def _open(req, timeout=None):
            if "models=best_match" in req.full_url:
                return FakeResp(b'{"daily": 1}')
            return op(req)
        argv = ["--data-dir", str(self.dir), "--today", TODAY, "--start-date", START.isoformat(),
                "--end-date", END.isoformat(), "--model", "era5", "--model", "best_match"]
        with mock.patch("fetch_data.urllib.request.urlopen", _open):
            self.assertEqual(fd.main(argv), 1)
        self.assertEqual(list(self.dir.glob("*.csv")), [])


def cloud_urlopen(rain, cc_fn=lambda i: 40 + (i % 50), sun_fn=lambda i: 20000.0, grid=(-22.75, -43.25), day_s=45000.0,
                  hourly_fn=lambda d, h: 30 + h, null_tail=0, end=END):
    """urlopen falso para chuva + nebulosidade (diário e horário), tudo da mesma célula."""
    def _open(req, timeout=None):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(req.full_url).query)
        s, e = date.fromisoformat(q["start_date"][0]), date.fromisoformat(q["end_date"][0])
        days = [(s + timedelta(days=i)) for i in range((e - s).days + 1)]
        body = {"latitude": grid[0], "longitude": grid[1], "elevation": 12.0}
        if "hourly" in q:
            times = [f"{d.isoformat()}T{h:02d}:00" for d in days for h in range(24)]
            body["hourly_units"] = {"time": "iso8601", "cloud_cover": "%"}
            body["hourly"] = {"time": times, "cloud_cover": [hourly_fn(date.fromisoformat(t[:10]), int(t[11:13]))
                                                             for t in times]}
        elif "cloud_cover_mean" in q["daily"][0]:
            ntot = (end - START).days + 1
            idx = [(d - START).days for d in days]
            body["daily_units"] = {"time": "iso8601", "cloud_cover_mean": "%", "sunshine_duration": "s",
                                   "daylight_duration": "s"}
            body["daily"] = {"time": [d.isoformat() for d in days],
                             "cloud_cover_mean": [None if i >= ntot - null_tail else cc_fn(i) for i in idx],
                             "sunshine_duration": [None if i >= ntot - null_tail else sun_fn(i) for i in idx],
                             "daylight_duration": [day_s for _ in idx]}
        else:
            body["daily_units"] = {"time": "iso8601", "precipitation_sum": "mm"}
            body["daily"] = {"time": [d.isoformat() for d in days],
                             "precipitation_sum": [rain.get(d.isoformat()) for d in days]}
        return FakeResp(json.dumps(body).encode())
    return _open


class TestCloud(Base):
    def run_cloud(self, rain, urlopen, *extra):
        argv = ["--data-dir", str(self.dir), "--today", TODAY, "--start-date", START.isoformat(),
                "--end-date", END.isoformat(), "--backoff", "0", "--retries", "0", *extra]
        # sem --model: baixa todos os modelos de chuva (o falso responde igual para todos) e a nebulosidade
        with mock.patch("fetch_data.urllib.request.urlopen", urlopen), mock.patch("fetch_data.time.sleep"):
            return fd.main(argv)

    def test_writes_cloud_csv_and_meta(self):
        rain = series()
        self.assertEqual(self.run_cloud(rain, cloud_urlopen(rain)), 0)
        lines = (self.dir / "era5_cloud.csv").read_text().splitlines()
        self.assertEqual(lines[0], "date,cloud_cover_mean_pct,sunshine_min,daylight_min,cloud_daytime_0917_pct")
        self.assertEqual(len(lines), 92)
        # 20000 s = 333 min (333,33 arredonda para 333); 45000 s = 750 min; média das horas 09..17 de 30+h = 43,0
        self.assertEqual(lines[1], "2024-01-01,40,333,750,43.0")
        meta = json.loads((self.dir / "meta.json").read_text())
        self.assertTrue(meta["cloud"]["same_grid_cell_as_rain_era5"])
        self.assertEqual(meta["cloud"]["returned_latitude"], -22.75)
        self.assertEqual(meta["cloud"]["null_days"], 0)
        self.assertIn("columns", meta["cloud"])

    def test_trailing_nulls_blank_daytime_too(self):
        rain = series(fn=lambda i: 1.0)
        for k in list(rain)[-3:]:
            rain[k] = None
        self.assertEqual(self.run_cloud(rain, cloud_urlopen(rain, null_tail=3)), 0)
        last = (self.dir / "era5_cloud.csv").read_text().splitlines()[-1]
        self.assertEqual(last, "2024-03-31,,,750,")
        self.assertEqual(json.loads((self.dir / "meta.json").read_text())["cloud"]["null_days"], 3)

    def test_default_model_run_skips_cloud_only_with_model(self):
        rain = series()
        self.assertEqual(self.run_main(rain), 0)               # --model era5: sem nebulosidade
        self.assertFalse((self.dir / "era5_cloud.csv").exists())

    def test_skip_cloud(self):
        rain = series()
        self.assertEqual(self.run_cloud(rain, make_urlopen(rain), "--skip-cloud"), 0)
        self.assertFalse((self.dir / "era5_cloud.csv").exists())

    def test_cloud_out_of_range_rejected_and_nothing_written(self):
        rain = series()
        self.assertEqual(self.run_cloud(rain, cloud_urlopen(rain, cc_fn=lambda i: 120 if i == 5 else 50)), 1)
        self.assertFalse((self.dir / "era5_cloud.csv").exists())
        self.assertFalse((self.dir / "era5.csv").exists())       # tudo ou nada, inclusive a chuva

    def test_sunshine_above_daylight_rejected(self):
        rain = series()
        self.assertEqual(self.run_cloud(rain, cloud_urlopen(rain, sun_fn=lambda i: 50000.0)), 1)
        self.assertFalse((self.dir / "era5_cloud.csv").exists())

    def test_grid_cell_mismatch_with_rain_rejected(self):
        rain = series()
        base = cloud_urlopen(rain)

        def mixed(req, timeout=None):
            if "cloud_cover" in req.full_url:
                return cloud_urlopen(rain, grid=(-22.9, -43.1))(req, timeout)
            return base(req, timeout)
        self.assertEqual(self.run_cloud(rain, mixed), 1)
        self.assertFalse((self.dir / "era5_cloud.csv").exists())

    def test_missing_hour_rejected(self):
        rain = series()
        self.assertEqual(self.run_cloud(rain, cloud_urlopen(
            rain, hourly_fn=lambda d, h: None if (d.day == 3 and h == 12) else 50)), 1)

    def test_cloud_revision_blocks_unless_allowed(self):
        rain = series()
        self.assertEqual(self.run_cloud(rain, cloud_urlopen(rain)), 0)
        bad = cloud_urlopen(rain, cc_fn=lambda i: 40 + (i % 50) + (10 if i == 0 else 0))
        self.assertEqual(self.run_cloud(rain, bad), 1)
        self.assertEqual(self.run_cloud(rain, bad, "--allow-revisions"), 0)

    def test_parse_cloud_hourly_daytime_mean(self):
        times = [f"2024-01-01T{h:02d}:00" for h in range(24)]
        out, _ = fd.parse_cloud_hourly({"hourly": {"time": times, "cloud_cover": list(range(24))},
                                        "hourly_units": {"cloud_cover": "%"}}, "u")
        self.assertEqual(out[date(2024, 1, 1)], 13.0)           # média de 9..17 = 13


class TestHttp(unittest.TestCase):
    def test_retries_then_succeeds(self):
        ok = FakeResp(b'{"a": 1}')
        seq = [urllib.error.URLError("boom"),
               urllib.error.HTTPError("u", 503, "x", {}, io.BytesIO(b"")), ok]

        def _open(req, timeout=None):
            r = seq.pop(0)
            if isinstance(r, Exception):
                raise r
            return r
        with mock.patch("fetch_data.urllib.request.urlopen", _open), \
                mock.patch("fetch_data.time.sleep") as sl:
            self.assertEqual(fd.http_get_json("http://x", retries=5, backoff=1), {"a": 1})
        self.assertEqual([c.args[0] for c in sl.call_args_list], [1, 2])

    def test_400_not_retried(self):
        calls = []

        def _open(req, timeout=None):
            calls.append(1)
            raise urllib.error.HTTPError("u", 400, "bad", {}, io.BytesIO(b'{"reason":"x"}'))
        with mock.patch("fetch_data.urllib.request.urlopen", _open), mock.patch("fetch_data.time.sleep"):
            with self.assertRaises(fd.ValidationError):
                fd.http_get_json("http://x")
        self.assertEqual(len(calls), 1)

    def test_gives_up_and_sends_user_agent(self):
        seen = []

        def _open(req, timeout=None):
            seen.append(req.get_header("User-agent"))
            raise urllib.error.URLError("down")
        with mock.patch("fetch_data.urllib.request.urlopen", _open), mock.patch("fetch_data.time.sleep"):
            with self.assertRaises(fd.ValidationError):
                fd.http_get_json("http://x", retries=2, backoff=0)
        self.assertEqual(len(seen), 3)
        self.assertIn("chuva-rio", seen[0])


if __name__ == "__main__":
    unittest.main()
