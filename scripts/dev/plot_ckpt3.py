"""Draw checkpoint 3 from an existing train or test log (no re-run)."""

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from slow2fast.generate import figure_title, parse_log

S1 = "#c45c26"
S2 = "#3d5a80"
SHARE = "#2e7d32"
PHASE_COLORS = {
    "single": "#f3efe8",
    "multi": "#e8eef3",
    "partial": "#ebe8f3",
    "random": "#e8f0ea",
}


def load_log(path):
    return parse_log(path.read_text())


def _share_steps(shares):
    xs, ys = [], []
    for index, (start, end, share) in enumerate(shares):
        xs.extend([start, end])
        ys.extend([share, share])
        if index + 1 < len(shares):
            xs.append(end)
            ys.append(shares[index + 1][2])
    return xs, ys


def draw(rows, out, mode, tasks):
    title = figure_title(mode, tasks)
    fig, ax = plt.subplots(figsize=(12, 3.8), layout="constrained")
    s1_x, s2_x = [], []
    ends = []
    shares = []
    phase_spans = []
    step = 0
    current_phase = None
    phase_start = 0.5

    for phase, name, sources, reached, *_rest in rows:
        if phase != current_phase:
            if current_phase is not None:
                phase_spans.append((current_phase, phase_start, step + 0.5))
            current_phase = phase
            phase_start = step + 0.5
        if not sources:
            mark_at = max(step, 1) if step == 0 else step
            ends.append((mark_at, name, reached, phase))
            shares.append((mark_at, mark_at, 1.0 if reached else 0.0))
            continue
        start = step + 1
        for source in sources:
            step += 1
            if source == "s1":
                s1_x.append(step)
            else:
                s2_x.append(step)
        share = sources.count("s1") / len(sources)
        shares.append((start, step, share))
        ends.append((step, name, reached, phase))

    if current_phase is not None:
        phase_spans.append((current_phase, phase_start, max(step, 1) + 0.5))

    for phase, left, right in phase_spans:
        ax.axvspan(left, right, color=PHASE_COLORS.get(phase, "#eeeeee"), zorder=0)
        ax.text(
            (left + right) / 2,
            1.28,
            phase,
            ha="center",
            va="bottom",
            fontsize=9,
            color="#5c5346",
        )

    ax.scatter(s2_x, [0] * len(s2_x), s=18, color=S2, label="System 2", zorder=3)
    ax.scatter(s1_x, [1] * len(s1_x), s=18, color=S1, label="System 1", zorder=3)

    for end, _name, reached, _phase in ends:
        ax.plot([end, end], [-0.18, 1.18], color="#b7aea4", linewidth=0.5, zorder=1)
        ax.scatter(
            [end],
            [-0.18],
            s=20,
            marker="o",
            facecolors="#5c5346" if reached else "none",
            edgecolors="#5c5346" if reached else "#a33b2b",
            linewidths=1.0,
            zorder=4,
        )

    xmax = max(step, 1)
    ax.set_xlim(0.4, xmax + 0.6)
    ax.set_ylim(-0.45, 1.45)
    ax.set_yticks([0, 1], ["System 2", "System 1"])
    ax.set_xlabel("Step")
    tick = 20 if xmax > 80 else 5
    ax.set_xticks(range(tick, xmax + 1, tick))
    ax.set_title(title, loc="left")
    ax.legend(loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.82, 1.22))

    share_ax = ax.twinx()
    if shares:
        share_ax.plot(*_share_steps(shares), color=SHARE, linewidth=1.4, zorder=2)
    share_ax.set_ylim(ax.get_ylim())
    share_ax.set_yticks([0, 0.5, 1])
    share_ax.set_ylabel("Share of System 1", color=SHARE)
    share_ax.tick_params(axis="y", colors=SHARE)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return title


def main():
    parser = argparse.ArgumentParser(description="Plot checkpoint 3 from a train or test log.")
    parser.add_argument(
        "--log",
        type=Path,
        default=None,
        help="Existing log to read (no re-run). Default: results/ckpt3_test.txt if present else train.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Where to write the figure. Defaults to results/ckpt3_{mode}.png from the log header.",
    )
    args = parser.parse_args()
    log = args.log
    if log is None:
        test_log = ROOT / "results" / "ckpt3_test.txt"
        train_log = ROOT / "results" / "ckpt3_train.txt"
        log = test_log if test_log.is_file() else train_log
    mode, tasks, rows = load_log(log)
    out = args.out or (ROOT / "results" / f"ckpt3_{mode}.png")
    title = draw(rows, out, mode=mode, tasks=tasks)
    print(out)
    print(title)


if __name__ == "__main__":
    main()
