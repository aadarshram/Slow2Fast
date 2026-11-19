"""Run the checkpoint 2 lesson sequence and the frozen final block."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from slow2fast.curriculum import FINALS, LESSONS, SCHEMAS, SkillLibrary, run_skill_episode


def main():
    parser = argparse.ArgumentParser(description="Run checkpoint 2 and write one row per task.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "results" / "ckpt2.txt",
        help="Where to write the lesson and frozen rows.",
    )
    parser.add_argument(
        "--known_rules",
        action="store_true",
        help="Use the hand-specified schemas instead of inducing rules from traces.",
    )
    args = parser.parse_args()
    library = SkillLibrary(known_rules=args.known_rules)
    lines = []
    for name, problem in LESSONS:
        result = run_skill_episode(problem, library, update=True)
        lines.append(_row(name, result, library.counts()))
    lines.append("")
    for name, problem in FINALS:
        result = run_skill_episode(problem, library, update=False)
        lines.append(_row(name + " frozen", result, library.counts()))
    text = "\n".join(lines) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text)
    print(text, end="")


def _row(name, result, counts):
    sources = " ".join(step.source for step in result.steps)
    if set(SCHEMAS) <= set(counts):
        keys = SCHEMAS
    else:
        keys = sorted(counts)
    counts_text = " ".join(f"{key} {counts[key]}" for key in keys)
    return (
        f"{name} sources {sources} s1_ok {result.s1_ok} "
        f"s2_steps {result.s2_steps} s1_bad {result.s1_bad} {counts_text}"
    )


if __name__ == "__main__":
    main()
