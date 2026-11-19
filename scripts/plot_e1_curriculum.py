"""Bar chart for e1_curriculum)."""

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CURRICULUM = "#c45c26"
NO_CURRICULUM = "#3d5a80"
CONDITIONS = (("curriculum", "Curriculum", CURRICULUM), ("no_curriculum", "No curriculum", NO_CURRICULUM))


def load(path):
    payload = json.loads(path.read_text())
    seeds = payload["seeds"]
    values = {cond: {"train": [], "test": []} for cond, _, _ in CONDITIONS}
    for seed in seeds:
        run = payload["runs"][str(seed)]["conditions"]
        for cond, _, _ in CONDITIONS:
            values[cond]["train"].append(run[cond]["train"])
            values[cond]["test"].append(run[cond]["test"])
    return payload, values


def draw(payload, values, out):
    groups = ["Train", "Test (held-out)"]
    keys = ["train", "test"]
    x = np.arange(len(groups))
    width = 0.32

    fig, ax = plt.subplots(figsize=(5.2, 3.6), layout="constrained")

    for i, (cond, label, color) in enumerate(CONDITIONS):
        offset = (i - 0.5) * width
        means = [np.mean(values[cond][k]) for k in keys]
        lo = [means[j] - min(values[cond][k]) for j, k in enumerate(keys)]
        hi = [max(values[cond][k]) - means[j] for j, k in enumerate(keys)]
        bars = ax.bar(x + offset, means, width, label=label, color=color, alpha=0.85, zorder=2)
        ax.errorbar(
            x + offset, means, yerr=[lo, hi], fmt="none", ecolor="#2b2b2b", elinewidth=1.1, capsize=3, zorder=3
        )
        for j, k in enumerate(keys):
            xs = np.full(len(values[cond][k]), x[j] + offset)
            rng = np.random.default_rng(0)
            xs = xs + rng.uniform(-0.04, 0.04, size=len(xs))
            ax.scatter(xs, values[cond][k], s=14, color="white", edgecolors=color, linewidths=1.0, zorder=4)

    ax.set_ylim(0, 1.05)
    ax.set_ylabel("System 1 share")
    ax.set_xticks(x, groups)
    ax.legend(loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 1.15))
    ax.spines[["top", "right"]].set_visible(False)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT / "results" / "curriculum_ablation.json")
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "curriculum_ablation.png")
    args = parser.parse_args()
    payload, values = load(args.data)
    draw(payload, values, args.out)
    print(args.out)


if __name__ == "__main__":
    main()
