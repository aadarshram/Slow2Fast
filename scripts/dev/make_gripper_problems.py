"""Write the Gripper stage-3 curriculum + random tail and a frozen holdout as PDDL problem files."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cmc import gripper_problems as GP
from cmc.pddl import PddlDomain


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--random-count", type=int, default=100)
    ap.add_argument("--test-count", type=int, default=100)
    a = ap.parse_args()
    domain = PddlDomain(ROOT / "domains" / "gripper" / "domain.pddl")
    import random

    from cmc.pddl import problem_text

    def dump(problems, folder):
        for i, p in enumerate(problems):
            path = a.out / folder / f"{i:03d}.pddl"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(problem_text(domain, f"{folder}-{i:03d}", p.object_types, p.initial, p.goal))

    dump(GP.stage3_train(domain, a.seed, a.random_count), "train")
    dump(GP.holdout(domain, a.seed, a.test_count), "test")
    print(f"wrote problems under {a.out}")


if __name__ == "__main__":
    main()
