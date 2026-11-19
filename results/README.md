# Results

Which script produced which file, matching the report's Setup / E1 / E2 / E3 / E4 / E5 / E6.

| Report section | Script | Result file |
| --- | --- | --- |
| E1 (curriculum vs no-curriculum) | `scripts/run_e1_curriculum.py` + `plot_e1_curriculum.py` | `curriculum_ablation.json` / `.pdf` |
| E2 (why System 2 is still called) | `scripts/run_e2_reasons.py` | `e2_reasons.json` |
| E3 (ablations) | `scripts/run_e3_ablation.py` | `e3_ablation.json` |
| E4 (BFS vs EHC teacher) | `scripts/run_e4_teacher_quality.py` | `e4_teacher_quality.json` |
| E5 (scaling to larger n) | `scripts/run_e5_scaling.py` + `plot_e5_scaling.py` | `e5_scaling.json` / `.pdf` |
| E6 (Gripper) | `scripts/run_gripper_table.py` | `gripper_bfs.txt`, `gripper_ehc.txt` |
| future-work line (Barman/Logistics) | `scripts/dev/run_bundle.py`, `scripts/dev/run_standard.py` | `standard_ehc.txt`, `outcomes_barman_bfs.txt` |

E2 and E3 also cross-check against `ckpt6_bfs.txt` / `ckpt6_ehc.txt`, produced by `scripts/run_sweep.py`
(a wider sweep that both scripts above were checked against; numbers match). Those two result files
are leftover from before the results got reorganized and will be folded into the main files above
in a later pass.

All `*.json` files above are raw per-seed data — rerunning the matching `plot_*.py` redraws the figure
without retraining anything.

`dev/` holds everything from earlier checkpoints and broader exploratory sweeps that aren't part of
the final report. Not deleted, just not part of the current story — see `slow2fast/dev/`, `scripts/dev/`,
`tests/dev/` for the matching code. Checkpoint results are grouped by number: `dev/ckpt1/` through
`dev/ckpt6/` (ckpt6 here is only the two heldout variants not already cross-checking E2/E3 above).
`dev/benchmarks_full.txt`, `bundle_vs_base.txt`, `gripper_*_heldout.txt`, and
`outcomes_min_barman_small.txt` are from the broader sweep, not tied to one checkpoint. Original
paths before the cleanup are in the git history (first commit).
