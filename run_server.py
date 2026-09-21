#!/usr/bin/env python3
"""Run the ecosystem sim with the browser UI.

Usage: python3 run_server.py [--port 8000] [--seed 7]
Then open http://127.0.0.1:8000
"""

import argparse

from sim.server import serve


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    serve(host=args.host, port=args.port, seed=args.seed)


if __name__ == "__main__":
    main()
