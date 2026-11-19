"""Line plot for e8_scaling."""

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

LINE = "#c45c26"
POINT = "#3d5a80"


def load(path):
    return json.loads(path.read_text())


def draw(payload, out):
    sizes = payload["test_sizes"]
    means = [np.mean(payload["runs"][str(n)]["test"]) for n in sizes]
    lo = [means[i] - min(payload["runs"][str(n)]["test"]) for i, n in enumerate(sizes)]
    hi = [max(payload["runs"][str(n)]["test"]) - means[i] for i, n in enumerate(sizes)]

    fig, ax = plt.subplots(figsize=(4.6, 3.4), layout="constrained")
    ax.errorbar(
        sizes, means, yerr=[lo, hi], fmt="o-", color=LINE, ecolor="#2b2b2b",
        elinewidth=1.1, capsize=3, markersize=6, linewidth=1.6, zorder=3,
    )
    rng = np.random.default_rng(0)
    for n in sizes:
        vals = payload["runs"][str(n)]["test"]
        xs = np.full(len(vals), n) + rng.uniform(-0.08, 0.08, size=len(vals))
        ax.scatter(xs, vals, s=14, color="white", edgecolors=POINT, linewidths=1.0, zorder=4)

    ax.axvline(payload["train_n"], color="#999999", linestyle="--", linewidth=1.0, zorder=1)
    ax.text(payload["train_n"], 1.0, "trained here", ha="center", va="bottom", fontsize=8, color="#666666")

    ax.set_xticks(sizes)
    ax.set_xlabel("Held-out problem size (max blocks, $n$)")
    ax.set_ylabel("System 1 share")
    ax.set_ylim(0, 1.08)
    ax.spines[["top", "right"]].set_visible(False)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT / "results" / "e8_scaling.json")
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "e8_scaling.pdf")
    args = parser.parse_args()
    payload = load(args.data)
    draw(payload, args.out)
    print(args.out)


if __name__ == "__main__":
    main()
