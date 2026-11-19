"""Why does System 2 still get called: no_match, multi_match, below_threshold?

induce-only (no refinement) vs. the full mechanism, same seeds and tasks as run_e1_curriculum.py.
Writes results/e2_reasons.json.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cmc.baselines import InduceOnly
from cmc.contrast_induce import ContrastLibrary
from cmc.domain import DOMAIN
from cmc.experiment import ensure_deterministic, evaluate, lessons_to_problems
from cmc.generate import test_holdout, train_curriculum

CONFIGS = {
    "induce_only": lambda: InduceOnly(),
    "full": lambda: ContrastLibrary(DOMAIN.operators, DOMAIN.apply, derived=True),
}
REASONS = ("no_match", "multi_match", "below_threshold", "loop_cut")


def main():
    ensure_deterministic()
    out = {name: {k: [] for k in REASONS + ("test",)} for name in CONFIGS}

    for seed in range(5):
        train = lessons_to_problems(
            DOMAIN, train_curriculum(n=4, practice=2, seed=seed, random_count=100), f"tr{seed}"
        )
        test = lessons_to_problems(DOMAIN, test_holdout(n=4, seed=seed, count=100), f"te{seed}")
        for name, factory in CONFIGS.items():
            result = evaluate(factory, "ehc", train, test)
            for k in REASONS:
                out[name][k].append(result["reasons"].get(k, 0))
            out[name]["test"].append(result["test"])
            print(seed, name, {k: out[name][k][-1] for k in REASONS}, "test", result["test"])

    out_path = ROOT / "results" / "e2_reasons.json"
    out_path.write_text(json.dumps(out, indent=2))
    print("wrote", out_path)


if __name__ == "__main__":
    main()
