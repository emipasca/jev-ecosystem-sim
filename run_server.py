#!/usr/bin/env python3
"""Run the ecosystem sim with the browser UI.

Usage: python3 run_server.py [--port 8000] [--seed 7] [--policy mock|jev]
Then open http://127.0.0.1:8000
"""

import argparse

from sim.policy import JevPolicy, MockPolicy
from sim.server import serve


def build_policy(name, seed):
    if name == "jev":
        return JevPolicy()
    return MockPolicy(seed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--policy", choices=["mock", "jev"], default="mock")
    args = ap.parse_args()
    policy = build_policy(args.policy, args.seed)
    print(f"policy: {args.policy}")
    serve(host=args.host, port=args.port, seed=args.seed, policy=policy)


if __name__ == "__main__":
    main()
