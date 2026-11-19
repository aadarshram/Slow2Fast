"""Train or test on the ckpt3 multi-tower generator."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cmc.generate import MODES, PHASES, make_problem, random_problem, run_mode


def main():
    parser = argparse.ArgumentParser(description="Multi-tower blocksworld generator / trainer.")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument(
        "--train",
        action="store_const",
        const="train",
        dest="mode",
        help="Run the scheduled curriculum with learning on.",
    )
    mode.add_argument(
        "--test",
        action="store_const",
        const="test",
        dest="mode",
        help="Load saved rules and run frozen random holdout tasks (no warmup).",
    )
    parser.add_argument("--n", type=int, default=4, help="Max blocks / bound for towers and heights.")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--phase",
        choices=PHASES,
        help="Emit a single problem in this phase instead of train/test.",
    )
    parser.add_argument("--practice", type=int, default=2, help="Repeats per shape roughly like threshold+1.")
    parser.add_argument(
        "--random-count",
        type=int,
        default=100,
        help="Number of tasks in the final train random phase (default 100).",
    )
    parser.add_argument(
        "--test-count",
        type=int,
        default=100,
        help="Number of frozen random holdout tasks when --test is set (default 100).",
    )
    parser.add_argument("--known_rules", action="store_true", help="Use hand schemas instead of induce.")
    parser.add_argument(
        "--rules",
        type=Path,
        default=None,
        help="Saved rules path. Train writes here; test loads from here. Default: results/ckpt3_rules.json.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Where to write the log. Defaults to results/ckpt3_{mode}.txt.",
    )
    args = parser.parse_args()

    if args.mode:
        if args.mode not in MODES:
            parser.error(f"unknown mode {args.mode}")
        out = args.out
        if out is None:
            out = ROOT / "results" / f"ckpt3_{args.mode}.txt"
        rules = args.rules or (ROOT / "results" / "ckpt3_rules.json")
        try:
            text, _library = run_mode(
                args.mode,
                n=args.n,
                practice=args.practice,
                seed=args.seed,
                random_count=args.random_count,
                test_count=args.test_count,
                known_rules=args.known_rules,
                rules_path=rules,
            )
        except FileNotFoundError as exc:
            parser.error(str(exc))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
        print(text, end="")
        print(f"wrote {out}", file=sys.stderr)
        if args.mode == "train":
            print(f"wrote {rules}", file=sys.stderr)
        return

    if args.phase:
        problem = make_problem(args.phase, n=args.n, seed=args.seed)
    else:
        problem = random_problem(n=args.n, seed=args.seed)
    print(f"blocks {problem.blocks}")
    print(f"initial {sorted(problem.initial)}")
    print(f"goal {sorted(problem.goal)}")


if __name__ == "__main__":
    main()
