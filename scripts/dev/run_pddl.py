"""Run the System 1 / System 2 loop on any PDDL domain, reading problems from files.

  python scripts/run_pddl.py --domain domains/blocksworld/domain.pddl \
      --train data/problems/bw_n4_s0/train --test data/problems/bw_n4_s0/test --s2 bfs

Train problems are run in filename order (that is the curriculum) with learning on; test problems are run
afterwards with the learned rules frozen. System 2 is pyperplan (ehc = enforced hill-climbing + hFF, bfs).
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from slow2fast.contrast_induce import ContrastLibrary
from slow2fast.experiment import ensure_deterministic, evaluate, pure_system2_work
from slow2fast.pddl import PddlDomain, load_problem


def load_dir(domain, folder):
    return [load_problem(domain, path) for path in sorted(Path(folder).glob("*.pddl"))]


def main():
    ensure_deterministic()
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", type=Path, required=True)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--test", type=Path, required=True)
    parser.add_argument("--s2", choices=("ehc", "bfs"), default="bfs")
    parser.add_argument("--no-derived", action="store_true", help="drop the sat/unsat goal-comparison features")
    parser.add_argument("--no-defer", action="store_true")
    parser.add_argument("--ties", action="store_true", help="tolerate proposals practice showed equally acceptable (needs --s2 bfs)")
    args = parser.parse_args()
    domain = PddlDomain(args.domain)
    train, test = load_dir(domain, args.train), load_dir(domain, args.test)
    factory = lambda: ContrastLibrary(
        domain.operators, domain.apply, derived=not args.no_derived, defer=not args.no_defer, ties=args.ties
    )
    out = evaluate(factory, args.s2, train, test)
    base = pure_system2_work(args.s2, test)
    r = out["reasons"]
    print(f"domain {domain.name}: {len(train)} train / {len(test)} test problems, System 2 = {args.s2}")
    print(f"solved {out['reach']}/{out['tasks']}  train S1 share {out['train']:.3f}  test S1 share {out['test']:.3f}")
    print(f"S1 precision {out['prec']:.3f}  plan length / optimal {out['overhead']:.3f}  rules {out['rules']}")
    print(f"System 2 work {out['work']} vs {base} for pure System 2 ({100 * out['work'] / max(1, base):.1f}%)")
    print("S2 calls by reason: " + " ".join(f"{k}={v}" for k, v in r.items()))
    for i, rule in enumerate(out["library"].rules):
        extra = [l for l in rule.lits if l not in rule.protected]
        print(f"  r{i} {rule.op}{rule.params} conf={rule.confirmations} + {extra}")


if __name__ == "__main__":
    main()
