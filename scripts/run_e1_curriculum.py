"""Curriculum vs. no-curriculum, same lesson budget, same held-out set per seed.

Writes results/curriculum_ablation.json (plot: scripts/plot_e1_curriculum.py).
"""

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from slow2fast.contrast_induce import ContrastLibrary
from slow2fast.domain import DOMAIN
from slow2fast.experiment import ensure_deterministic, evaluate, lessons_to_problems
from slow2fast.generate import random_problem, test_holdout, train_curriculum


def no_curriculum_lessons(n, seed, count, name_prefix="t"):
    """`count` lessons, all randomly generated multi-tower tasks, no staged phases."""
    rng = random.Random(seed)
    return [
        ("random", f"random-{i + 1}", random_problem(n=n, seed=rng.randint(0, 10**9), name_prefix=name_prefix))
        for i in range(count)
    ]


def library_factory():
    return ContrastLibrary(DOMAIN.operators, DOMAIN.apply, derived=True)


def run_one(seed, n, practice, kind):
    curriculum_lessons = train_curriculum(n=n, practice=practice, seed=seed, random_count=100)
    budget = len(curriculum_lessons)
    plain_lessons = no_curriculum_lessons(n=n, seed=seed, count=budget)

    test_lessons = test_holdout(n=n, seed=seed, count=100)
    test = lessons_to_problems(DOMAIN, test_lessons, f"te{seed}")

    out = {}
    for condition, lessons in (("curriculum", curriculum_lessons), ("no_curriculum", plain_lessons)):
        train = lessons_to_problems(DOMAIN, lessons, f"tr{seed}-{condition}")
        result = evaluate(library_factory, kind, train, test)
        result.pop("library")
        out[condition] = result
    return budget, out


def main():
    ensure_deterministic()
    parser = argparse.ArgumentParser()
    parser.add_argument("--s2", choices=("ehc", "bfs"), default="ehc")
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--n", type=int, default=4)
    parser.add_argument("--practice", type=int, default=2)
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "curriculum_ablation.json")
    args = parser.parse_args()

    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    payload = {
        "s2": args.s2,
        "n": args.n,
        "practice": args.practice,
        "seeds": seeds,
        "library": "contrast + sat/unsat",
        "runs": {},
    }

    print(f"{'seed':>4s} {'budget':>6s} {'cond':14s} {'train':>6s} {'test':>6s} {'rules':>6s}")
    for seed in seeds:
        budget, out = run_one(seed, args.n, args.practice, args.s2)
        payload["runs"][str(seed)] = {"budget": budget, "conditions": out}
        for condition, result in out.items():
            print(
                f"{seed:4d} {budget:6d} {condition:14s} {result['train']:6.3f} {result['test']:6.3f} {result['rules']:6d}",
                flush=True,
            )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2))
    print(f"\nwrote {args.out}")

    for condition in ("curriculum", "no_curriculum"):
        train_vals = [payload["runs"][str(s)]["conditions"][condition]["train"] for s in seeds]
        test_vals = [payload["runs"][str(s)]["conditions"][condition]["test"] for s in seeds]
        print(
            f"{condition:14s} train mean={statistics.mean(train_vals):.3f} "
            f"(range {min(train_vals):.3f}-{max(train_vals):.3f})  "
            f"test mean={statistics.mean(test_vals):.3f} (range {min(test_vals):.3f}-{max(test_vals):.3f})"
        )


if __name__ == "__main__":
    main()
