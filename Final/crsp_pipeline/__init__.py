"""CRSP extraction, normalization, and audit pipeline for the Conservative Formula study.

Stages (see README.md, "CRSP data pipeline"):
  extract   WRDS PostgreSQL -> data/raw/*.parquet            (needs WRDS credentials)
  build     data/raw -> normalized panel, benchmark, audits    (offline, deterministic)
"""
