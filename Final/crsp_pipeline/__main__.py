"""Command line: run from the Final folder.

  python -m crsp_pipeline extract --user <wrds_username> [--library crsp] [--end 2024-12-31]
  python -m crsp_pipeline build
  python -m crsp_pipeline all --user <wrds_username>
"""
import argparse

from . import config


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m crsp_pipeline")
    ap.add_argument("stage", choices=["extract", "build", "all"])
    ap.add_argument("--user", help="WRDS username (extract)")
    ap.add_argument("--library", default="crsp", help="WRDS CRSP schema; e.g. crsp_a_stock")
    ap.add_argument("--end", default=config.EXTRACT_END)
    args = ap.parse_args(argv)
    if args.stage in {"extract", "all"}:
        if not args.user:
            ap.error("--user is required for extract")
        from .extract import extract
        extract(args.user, args.library, config.EXTRACT_START, args.end)
    if args.stage in {"build", "all"}:
        from .build import build
        build(end=args.end)


if __name__ == "__main__":
    main()
