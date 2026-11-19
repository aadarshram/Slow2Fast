"""Train on one three-block tower and test on one four-block tower."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cmc.blocksworld import Tower
from cmc.episode import run_episode
from cmc.library import Library


def main():
    parser = argparse.ArgumentParser(description="Run checkpoint 1 and write the step counts.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "results" / "ckpt1.txt",
        help="Where to write the training and test counts.",
    )
    args = parser.parse_args()
    library = Library()
    train = run_episode(Tower(["a", "b", "c"]), library, update=True)
    test = run_episode(Tower(["w", "x", "y", "z"]), library, update=False)
    text = "\n".join(
        [
            "train tower a on b on c",
            f"goal_reached {train.goal_reached}",
            f"s1_ok {train.s1_ok}",
            f"s1_bad {train.s1_bad}",
            f"s2_steps {train.s2_steps}",
            f"sources {' '.join(step.source for step in train.steps)}",
            f"stack_confirmations {library.confirmation_count('stack')}",
            "",
            "test tower w on x on y on z (library frozen)",
            f"goal_reached {test.goal_reached}",
            f"s1_ok {test.s1_ok}",
            f"s1_bad {test.s1_bad}",
            f"s2_steps {test.s2_steps}",
            f"sources {' '.join(step.source for step in test.steps)}",
            f"stack_confirmations {library.confirmation_count('stack')}",
            "",
        ]
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
