"""``python -m dom`` -> start the web app. ``python -m dom SYMBOL`` -> one-shot CLI analysis."""

from __future__ import annotations

import sys


def main() -> None:
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        from .cli import main as cli_main

        cli_main(sys.argv[1:])
        return

    import argparse

    import uvicorn

    p = argparse.ArgumentParser(description="Binance DOM web app")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--reload", action="store_true")
    args = p.parse_args()
    uvicorn.run("dom.server:app", host=args.host, port=args.port, reload=args.reload, log_level="info")


if __name__ == "__main__":
    main()
