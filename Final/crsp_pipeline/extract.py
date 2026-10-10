"""Extract raw legacy-format CRSP monthly tables from WRDS into data/raw/*.parquet.

Connection: WRDS PostgreSQL (wrds-pgdata.wharton.upenn.edu:9737, SSL). The password is read by
libpq from the standard pgpass file (%APPDATA%\\postgresql\\pgpass.conf on Windows,
~/.pgpass elsewhere), from the WRDS_PASSWORD environment variable, or interactively. WRDS may
send a Duo push on first login. Nothing here stores credentials.

Every table is checked against `information_schema` before it is queried, so a renamed or missing
field fails immediately with a clear message instead of producing a partial extract.
"""
from __future__ import annotations

import datetime as dt
import getpass
import json
import os
import sys

import pandas as pd

from . import config
from .provenance import sha256

HOST, PORT, DBNAME = "wrds-pgdata.wharton.upenn.edu", 9737, "wrds"

COMMON_PERMNOS = ("(select distinct permno from {lib}.msenames "
                  "where shrcd in " + str(config.COMMON_SHARE_CODES) + ")")

# name -> (schema, table, columns, where clause, date column used for chunking or None)
TABLES = {
    "msenames": ("{lib}", "msenames",
                 ["permno", "permco", "namedt", "nameendt", "shrcd", "exchcd", "siccd",
                  "ticker", "comnam", "shrcls"],
                 "permno in " + COMMON_PERMNOS, None),
    "msf": ("{lib}", "msf",
            ["permno", "permco", "date", "ret", "retx", "prc", "shrout", "cfacpr", "cfacshr", "vol"],
            "date between %(start)s and %(end)s and permno in " + COMMON_PERMNOS, "date"),
    "msedelist": ("{lib}", "msedelist",
                  ["permno", "dlstdt", "dlstcd", "dlret", "dlretx", "dlprc", "nwperm"],
                  "permno in " + COMMON_PERMNOS, None),
    "msedist": ("{lib}", "msedist",
                ["permno", "distcd", "divamt", "facpr", "facshr", "dclrdt", "exdt", "rcrddt", "paydt"],
                "permno in " + COMMON_PERMNOS, None),
    "msi": ("{lib}", "msi", ["date", "vwretd", "vwretx", "ewretd", "totval", "totcnt"],
            "date between %(start)s and %(end)s", None),
    "ff_factors": ("ff", "factors_monthly", ["dateff", "mktrf", "smb", "hml", "rf", "umd"],
                   "dateff between %(start)s and %(end)s", None),
}


def build_query(name: str, library: str) -> str:
    schema, table, cols, where, _ = TABLES[name]
    schema = schema.format(lib=library)
    return (f"select {', '.join(cols)} from {schema}.{table} "
            f"where {where.format(lib=library)}")


def connect(username: str):
    import sqlalchemy as sa
    password = os.environ.get("WRDS_PASSWORD")
    if password is None and not _pgpass_exists() and sys.stdin.isatty():
        password = getpass.getpass(f"WRDS password for {username}: ")
    url = sa.engine.URL.create("postgresql+psycopg2", username=username, password=password,
                               host=HOST, port=PORT, database=DBNAME)
    return sa.create_engine(url, connect_args={"sslmode": "require",
                                               "application_name": "conservative_formula"})


def _pgpass_exists() -> bool:
    if os.environ.get("PGPASSFILE"):
        return os.path.exists(os.environ["PGPASSFILE"])
    if os.name == "nt":
        return os.path.exists(os.path.join(os.environ.get("APPDATA", ""), "postgresql", "pgpass.conf"))
    return os.path.exists(os.path.expanduser("~/.pgpass"))


def check_schema(conn, name: str, library: str) -> None:
    schema, table, cols, _, _ = TABLES[name]
    schema = schema.format(lib=library)
    found = pd.read_sql(
        "select column_name from information_schema.columns "
        "where table_schema = %(s)s and table_name = %(t)s",
        conn, params={"s": schema, "t": table})["column_name"].str.lower()
    if found.empty:
        raise RuntimeError(f"{schema}.{table} is not visible to this WRDS account. "
                           "Check the subscription, or pass --library (e.g. crsp_a_stock).")
    missing = sorted(set(cols) - set(found))
    if missing:
        raise RuntimeError(f"{schema}.{table} lacks expected columns {missing}. The legacy SIZ "
                           "layout is required; CIZ (v2) tables use different names and conventions.")


def decade_chunks(start: str, end: str):
    lo, hi = pd.Timestamp(start), pd.Timestamp(end)
    edges = [lo] + [pd.Timestamp(f"{y}-01-01") for y in range(lo.year // 10 * 10 + 10, hi.year + 1, 10)]
    for a, b in zip(edges, edges[1:] + [hi + pd.Timedelta(days=1)]):
        yield a.date().isoformat(), (b - pd.Timedelta(days=1)).date().isoformat()


def extract(username: str, library: str = "crsp", start: str = config.EXTRACT_START,
            end: str = config.EXTRACT_END) -> dict:
    config.RAW.mkdir(parents=True, exist_ok=True)
    engine = connect(username)
    log = {"extracted_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "host": HOST, "library": library, "start": start, "end": end, "tables": {}}
    with engine.connect() as conn:
        for name in TABLES:
            check_schema(conn, name, library)
        for name, spec in TABLES.items():
            sql = build_query(name, library)
            chunks = list(decade_chunks(start, end)) if spec[4] else [(start, end)]
            frames = []
            for a, b in chunks:
                print(f"  {name}: {a} .. {b}", flush=True)
                frames.append(pd.read_sql(sql, conn, params={"start": a, "end": b}))
            df = pd.concat(frames, ignore_index=True)
            path = config.RAW / f"{name}.parquet"
            df.to_parquet(path, index=False, compression="zstd")
            log["tables"][name] = {"sql": sql, "rows": len(df), "file": path.name, "sha256": sha256(path)}
            print(f"  {name}: {len(df):,} rows -> {path.name}", flush=True)
        log["msf_max_date"] = str(pd.read_sql(f"select max(date) as d from {library}.msf", conn)["d"].iloc[0])
    (config.RAW / "extract_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    return log
