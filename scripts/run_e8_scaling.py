"""Train once at n=4, freeze, test on held-out sets of increasing size.

Writes results/e8_scaling.json.
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
from slow2fast.experiment import ensure_deterministic, lessons_to_problems
from slow2fast.generate import test_holdout, train_curriculum
from slow2fast.system2 import System2, run_episode


def library_factory():
    return ContrastLibrary(DOMAIN.operators, DOMAIN.apply, derived=True)


def train_library(seed, train_n, practice, kind, budget=None):
    library = library_factory()
    s2 = System2(kind, budget=budget)
    train = lessons_to_problems(
        DOMAIN, train_curriculum(n=train_n, practice=practice, seed=seed, random_count=100), f"tr{seed}"
    )
    train_sources = []
    for problem in train:
        result = run_episode(problem, library, s2, update=True)
        train_sources += [step.source for step in result.steps]
    train_share = train_sources.count("s1") / max(1, len(train_sources))
    return library, train_share


def evaluate_frozen(library, test, kind, budget=None):
    s2 = System2(kind, budget=budget)
    reached = steps = s1 = 0
    for problem in test:
        result = run_episode(problem, library, s2, update=False)
        reached += int(result.goal_reached)
        steps += len(result.steps)
        s1 += result.s1_ok
    return {"test": s1 / max(1, steps), "reach": reached, "tasks": len(test)}


def main():
    ensure_deterministic()
    parser = argparse.ArgumentParser()
    parser.add_argument("--s2", choices=("ehc", "bfs"), default="ehc")
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--train-n", type=int, default=4)
    parser.add_argument("--practice", type=int, default=2)
    parser.add_argument("--test-sizes", type=int, nargs="+", default=[4, 5, 6, 8])
    parser.add_argument("--test-count", type=int, default=100)
    parser.add_argument("--budget", type=int, default=20000, help="expansion cap per plan() call; 0 = unbounded")
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "e8_scaling.json")
    args = parser.parse_args()
    budget = args.budget or None

    seeds = list(range(args.seeds))
    out = {str(n): {"test": [], "reach": []} for n in args.test_sizes}
    train_shares = []

    def save():
        payload = {
            "s2": args.s2,
            "train_n": args.train_n,
            "practice": args.practice,
            "budget": budget,
            "seeds_done": len(train_shares),
            "seeds": seeds,
            "test_sizes": args.test_sizes,
            "test_count": args.test_count,
            "train_shares": train_shares,
            "runs": out,
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2))

    for seed in seeds:
        library, train_share = train_library(seed, args.train_n, args.practice, args.s2, budget=budget)
        train_shares.append(train_share)
        print(f"seed={seed} trained at n={args.train_n} train_share={train_share:.3f}", flush=True)
        for n in args.test_sizes:
            test = lessons_to_problems(DOMAIN, test_holdout(n=n, seed=seed, count=args.test_count), f"te{seed}-n{n}")
            result = evaluate_frozen(library, test, args.s2, budget=budget)
            out[str(n)]["test"].append(result["test"])
            out[str(n)]["reach"].append(result["reach"])
            print(
                f"  n={n:3d} test_share={result['test']:.3f} reach={result['reach']}/{result['tasks']}",
                flush=True,
            )
        save()  # incremental: never lose a finished seed if a later one stalls

    print(f"\nwrote {args.out}\n")

    print(f"train (n={args.train_n}): mean={statistics.mean(train_shares):.3f}")
    for n in args.test_sizes:
        vals = out[str(n)]["test"]
        reach = out[str(n)]["reach"]
        print(
            f"n={n:3d}  test_share mean={statistics.mean(vals):.3f} std={statistics.stdev(vals):.3f}  "
            f"reach={sum(reach)}/{len(seeds) * args.test_count}"
        )


if __name__ == "__main__":
    main()
