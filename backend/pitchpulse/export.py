"""Export synthetic matches as JSON Lines: python -m pitchpulse.export --seeds 7 11 23 --out ../data"""

import argparse
import json
from pathlib import Path

from .simulator import generate_match


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[7])
    ap.add_argument("--out", default="../data")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for seed in args.seeds:
        path = out / f"match_seed{seed}.jsonl"
        with path.open("w") as f:
            for ev in generate_match(seed=seed):
                f.write(json.dumps(ev) + "\n")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
