"""BFS vs EHC as System 2, full mechanism.

Writes results/e4_teacher_quality.json.
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from slow2fast.contrast_induce import ContrastLibrary
from slow2fast.domain import DOMAIN
from slow2fast.experiment import ensure_deterministic, evaluate, lessons_to_problems
from slow2fast.generate import test_holdout, train_curriculum

METRICS = ("train", "test", "rules", "prec", "overhead")
REASONS = ("no_match", "multi_match", "below_threshold", "loop_cut")


def library_factory():
    return ContrastLibrary(DOMAIN.operators, DOMAIN.apply, derived=True)


def main():
    ensure_deterministic()
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--n", type=int, default=4)
    parser.add_argument("--practice", type=int, default=2)
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "e4_teacher_quality.json")
    args = parser.parse_args()

    seeds = list(range(args.seeds))
    out = {kind: {m: [] for m in METRICS + REASONS} for kind in ("bfs", "ehc")}

    for seed in seeds:
        train = lessons_to_problems(
            DOMAIN, train_curriculum(n=args.n, practice=args.practice, seed=seed, random_count=100), f"tr{seed}"
        )
        test = lessons_to_problems(DOMAIN, test_holdout(n=args.n, seed=seed, count=100), f"te{seed}")
        for kind in ("bfs", "ehc"):
            result = evaluate(library_factory, kind, train, test)
            for m in METRICS:
                out[kind][m].append(result[m])
            for key in REASONS:
                out[kind][key].append(result["reasons"].get(key, 0))
            print(
                f"seed={seed} s2={kind:3s} train={result['train']:.3f} test={result['test']:.3f} "
                f"overhead={result['overhead']:.3f} rules={result['rules']} prec={result['prec']:.3f}",
                flush=True,
            )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"n": args.n, "practice": args.practice, "seeds": seeds, "runs": out}, indent=2))
    print(f"\nwrote {args.out}\n")

    header = f"{'s2':6s}" + "".join(f"{m:>14s}" for m in METRICS + REASONS)
    print(header)
    for kind in ("bfs", "ehc"):
        row = f"{kind:6s}"
        for m in METRICS + REASONS:
            vals = out[kind][m]
            mean = statistics.mean(vals)
            std = statistics.stdev(vals) if len(vals) > 1 else 0.0
            row += f"{mean:7.3f}±{std:5.3f}"
        print(row)


if __name__ == "__main__":
    main()
