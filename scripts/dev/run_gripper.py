"""Gripper, in stages (see docs/gripper.md).

  --stage 1   a handful of rules: one ball, two rooms, two grippers
  --stage 2   a deliberate curriculum, tested on fresh problems of the same kinds and on random ones
  --stage 3   the curriculum followed by a random tail, tested on frozen random problems and larger ones
"""

import argparse
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from slow2fast import gripper_problems as GP
from slow2fast.contrast_induce import ContrastLibrary
from slow2fast.experiment import ensure_deterministic, evaluate, pure_system2_work
from slow2fast.pddl import PddlDomain

DOMAIN = PddlDomain(ROOT / "domains" / "gripper" / "domain.pddl")


def factory(**kw):
    return lambda: ContrastLibrary(DOMAIN.operators, DOMAIN.apply, **kw)


def report(label, out, base):
    r = out["reasons"]
    print(f"{label:34s} solved {out['reach']:3d}/{out['tasks']:<3d} S1 share {out['test']:.3f}  prec {out['prec']:.3f}  "
          f"len/opt {out['overhead']:.3f}  rules {out['rules']:2d}  S2 cost {100 * out['work'] / max(1, base):5.1f}%  "
          f"S2 calls: " + " ".join(f"{k}={v}" for k, v in r.items() if v))


def show_rules(library):
    for i, rule in enumerate(library.rules):
        extra = [l for l in rule.lits if l not in rule.protected]
        print(f"   r{i} {rule.op}{rule.params} conf={rule.confirmations} defer={sorted(rule.defer)}\n        + {extra}")


def main():
    ensure_deterministic()
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=int, choices=(1, 2, 3), required=True)
    parser.add_argument("--s2", choices=("ehc", "bfs"), default="bfs")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--rules", action="store_true", help="print the learned rules")
    parser.add_argument("--no-derived", action="store_true")
    parser.add_argument("--no-full-cover", action="store_true")
    parser.add_argument("--ties", action="store_true", help="tolerate proposals practice showed equally acceptable")
    parser.add_argument("--seeds", type=int, default=1, help="average the stage-3 holdout over this many seeds")
    args = parser.parse_args()
    kw = dict(derived=not args.no_derived, ties=args.ties, full_cover=not args.no_full_cover)
    rng = random.Random(args.seed)
    if args.stage == 1:
        train = GP.stage1(DOMAIN, rng, 6, "t")
        tests = {"fresh stage-1 problems": GP.stage1(DOMAIN, random.Random(args.seed + 99), 30, "h")}
    elif args.stage == 2:
        train = [p for _ph, p in GP.stage2(DOMAIN, rng, 3, "t")]
        fresh = random.Random(args.seed + 99)
        tests = {"fresh curriculum-shaped": [p for _ph, p in GP.stage2(DOMAIN, fresh, 3, "h")],
                 "random (2-3 rooms, <=4 balls)": GP.holdout(DOMAIN, args.seed, 60)}
    else:
        train = GP.stage3_train(DOMAIN, args.seed, 100)
        tests = {"random holdout": GP.holdout(DOMAIN, args.seed, 100)}
    print(f"stage {args.stage}, System 2 = pyperplan {args.s2}, {len(train)} training problems")
    for label, test in tests.items():
        out = evaluate(factory(**kw), args.s2, train, test)
        report(label, out, pure_system2_work(args.s2, test))
    print(f"train S1 share {out['train']:.3f}")
    if args.rules:
        show_rules(out["library"])


if __name__ == "__main__":
    main()
