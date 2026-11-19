"""E4: which individual design choices in the refinement mechanism are load-bearing?

Same protocol as E1/E2: blocksworld, n=4, System 2 = EHC, curriculum training
(cmc.generate.train_curriculum), 100 held-out test tasks, 5 seeds. Each row removes (or, for
threshold, weakens) exactly one design choice from the full mechanism (contrast + sat/unsat)
and reports the effect on System 1 share and on the no_match/multi_match/below_threshold
diagnostic breakdown.

Saves full per-seed results to results/e4_ablation.json so the table/figure can be rebuilt
without rerunning.
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cmc.contrast_induce import ContrastLibrary
from cmc.domain import DOMAIN
from cmc.experiment import ensure_deterministic, evaluate, lessons_to_problems
from cmc.generate import test_holdout, train_curriculum


def lib(**kw):
    return lambda: ContrastLibrary(DOMAIN.operators, DOMAIN.apply, derived=True, **kw)


CONFIGS = {
    "full": lib(),
    "no_merge": lib(merge=False),
    "no_deferral_link": lib(defer=False),
    "no_symmetry": lib(symmetry=False),
    "spec_after_1_clash": lib(spec_threshold=1),
    "no_negated_literals": lib(allow_neg=False),
    "no_full_cover": lib(full_cover=False),
    "threshold_1": lib(threshold=1),
}

METRICS = ("train", "test", "rules")
REASONS = ("no_match", "multi_match", "below_threshold", "loop_cut")


def main():
    ensure_deterministic()
    parser = argparse.ArgumentParser()
    parser.add_argument("--s2", choices=("ehc", "bfs"), default="ehc")
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--n", type=int, default=4)
    parser.add_argument("--practice", type=int, default=2)
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "e4_ablation.json")
    args = parser.parse_args()

    seeds = list(range(args.seeds))
    out = {name: {m: [] for m in METRICS + REASONS} for name in CONFIGS}

    for seed in seeds:
        train = lessons_to_problems(
            DOMAIN, train_curriculum(n=args.n, practice=args.practice, seed=seed, random_count=100), f"tr{seed}"
        )
        test = lessons_to_problems(DOMAIN, test_holdout(n=args.n, seed=seed, count=100), f"te{seed}")
        for name, factory in CONFIGS.items():
            result = evaluate(factory, args.s2, train, test)
            out[name]["train"].append(result["train"])
            out[name]["test"].append(result["test"])
            out[name]["rules"].append(result["rules"])
            for key in REASONS:
                out[name][key].append(result["reasons"].get(key, 0))
            print(
                f"seed={seed} {name:20s} train={result['train']:.3f} test={result['test']:.3f} "
                f"rules={result['rules']} multi={result['reasons'].get('multi_match', 0)}",
                flush=True,
            )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"s2": args.s2, "n": args.n, "practice": args.practice, "seeds": seeds, "runs": out}, indent=2))
    print(f"\nwrote {args.out}\n")

    header = f"{'config':20s}" + "".join(f"{m:>14s}" for m in METRICS + REASONS)
    print(header)
    for name in CONFIGS:
        row = f"{name:20s}"
        for m in METRICS + REASONS:
            vals = out[name][m]
            mean = statistics.mean(vals)
            std = statistics.stdev(vals) if len(vals) > 1 else 0.0
            row += f"{mean:7.3f}±{std:5.3f}"
        print(row)


if __name__ == "__main__":
    main()
