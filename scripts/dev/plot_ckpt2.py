"""Draw the checkpoint 2 figure along the step axis, with a mark at each task end."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from cmc.curriculum import FINALS, LESSONS, SkillLibrary, run_skill_episode

S1 = "#c45c26"
S2 = "#3d5a80"
SHARE = "#2e7d32"


def collect():
    library = SkillLibrary(known_rules=True)
    rows = []
    for name, problem in LESSONS:
        result = run_skill_episode(problem, library, update=True)
        rows.append((name, [step.source for step in result.steps], result.goal_reached, False))
    for name, problem in FINALS:
        result = run_skill_episode(problem, library, update=False)
        rows.append((name, [step.source for step in result.steps], result.goal_reached, True))
    return rows


def _share_steps(shares):
    xs, ys = [], []
    for index, (start, end, share) in enumerate(shares):
        xs.append(start)
        ys.append(share)
        xs.append(end)
        ys.append(share)
        if index + 1 < len(shares):
            xs.append(end)
            ys.append(shares[index + 1][2])
    return xs, ys


def draw(rows, out):
    fig, ax = plt.subplots(figsize=(11, 3.8), layout="constrained")
    s1_x, s2_x = [], []
    ends = []
    shares = []
    step = 0
    frozen_at = None
    for name, sources, reached, frozen in rows:
        if frozen and frozen_at is None:
            frozen_at = step + 0.5
        if not sources:
            ends.append((step, name, reached))
            continue
        start = step + 1
        for source in sources:
            step += 1
            if source == "s1":
                s1_x.append(step)
            else:
                s2_x.append(step)
        shares.append((start, step, sources.count("s1") / len(sources)))
        ends.append((step, name, reached))
    if frozen_at is not None:
        ax.axvspan(frozen_at, step + 0.5, color="#ece7df", zorder=0)
        ax.text(frozen_at + 0.4, 1.18, "frozen", fontsize=9, color="#5c5346")
    ax.scatter(s2_x, [0] * len(s2_x), s=28, color=S2, label="System 2", zorder=3)
    ax.scatter(s1_x, [1] * len(s1_x), s=28, color=S1, label="System 1", zorder=3)
    for end, _name, reached in ends:
        if end <= 0:
            continue
        ax.plot([end, end], [-0.18, 1.18], color="#b7aea4", linewidth=0.7, zorder=1)
        ax.scatter(
            [end],
            [-0.18],
            s=36,
            marker="o",
            facecolors="#5c5346" if reached else "none",
            edgecolors="#5c5346" if reached else "#a33b2b",
            linewidths=1.2,
            zorder=4,
        )
    ax.set_xlim(0.4, step + 0.6)
    ax.set_ylim(-0.45, 1.45)
    ax.set_yticks([0, 1], ["System 2", "System 1"])
    ax.set_xlabel("Step")
    ax.set_xticks(range(5, step + 1, 5))
    ax.set_title("Checkpoint 2", loc="left")
    ax.legend(loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.72, 1.28))
    share_ax = ax.twinx()
    share_ax.plot(*_share_steps(shares), color=SHARE, linewidth=1.6, zorder=2)
    share_ax.set_ylim(ax.get_ylim())
    share_ax.set_yticks([0, 0.5, 1])
    share_ax.set_ylabel("Share of System 1", color=SHARE)
    share_ax.tick_params(axis="y", colors=SHARE)
    tax = ax.secondary_xaxis("top")
    tax.set_xticks(
        [end for end, _name, _reached in ends if end > 0],
        [name for end, name, _reached in ends if end > 0],
        rotation=45,
        ha="left",
        fontsize=8,
    )
    tax.set_xlabel("")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Draw the checkpoint 2 figure.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "results" / "ckpt2.png",
        help="Where to write the figure.",
    )
    args = parser.parse_args()
    draw(collect(), args.out)
    print(args.out)


if __name__ == "__main__":
    main()
