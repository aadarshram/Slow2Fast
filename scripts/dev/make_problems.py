"""Write the blocksworld curriculum and frozen holdout as PDDL problem files.

The generator is the one domain-specific piece (it knows what a sensible blocksworld task is); everything
downstream reads the .pddl files only. Train files are numbered in curriculum order.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cmc.generate import test_holdout, train_curriculum
from cmc.pddl import PddlDomain, problem_from_atoms


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", type=Path, default=ROOT / "domains" / "blocksworld" / "domain.pddl")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--n", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--practice", type=int, default=2)
    parser.add_argument("--random-count", type=int, default=100)
    parser.add_argument("--test-count", type=int, default=100)
    args = parser.parse_args()
    domain = PddlDomain(args.domain)
    train = train_curriculum(n=args.n, practice=args.practice, seed=args.seed, random_count=args.random_count)
    for i, (phase, _name, p) in enumerate(train):
        problem_from_atoms(domain, f"train-{i:03d}-{phase}", p.blocks, p.initial, p.goal,
                           save_to=args.out / "train" / f"{i:03d}_{phase}.pddl")
    for i, (phase, _name, p) in enumerate(test_holdout(n=args.n, seed=args.seed, count=args.test_count)):
        problem_from_atoms(domain, f"test-{i:03d}", p.blocks, p.initial, p.goal,
                           save_to=args.out / "test" / f"{i:03d}.pddl")
    print(f"wrote {len(train)} train and {args.test_count} test problems under {args.out}")


if __name__ == "__main__":
    main()
