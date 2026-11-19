# Results

Which script produced which file, matching the report's Setup / E1 / E2 / E4 / E6 / E7 / E8.

| Report section | Script | Result file |
| --- | --- | --- |
| E1 (curriculum vs no-curriculum) | `scripts/run_e1_curriculum.py` + `plot_e1_curriculum.py` | `curriculum_ablation.json` / `.pdf` |
| E2 (why System 2 is still called) | `scripts/run_e2_reasons.py` | `e2_reasons.json` |
| E4 (ablations) | `scripts/run_e4_ablation.py` | `e4_ablation.json` |
| E6 (BFS vs EHC teacher) | `scripts/run_e6_teacher_quality.py` | `e6_teacher_quality.json` |
| E7 (Gripper) | `scripts/run_gripper_table.py` | `gripper_bfs.txt`, `gripper_ehc.txt` |
| E8 (scaling to larger n) | `scripts/run_e8_scaling.py` + `plot_e8_scaling.py` | `e8_scaling.json` / `.pdf` |
| future-work line (Barman/Logistics) | `scripts/dev/run_bundle.py`, `scripts/dev/run_standard.py` | `standard_ehc.txt`, `outcomes_barman_bfs.txt` |

E2 and E4 also cross-check against `ckpt6_bfs.txt` / `ckpt6_ehc.txt`, produced by `scripts/run_ckpt6.py`
(a wider sweep that both scripts above were checked against; numbers match).

All `*.json` files above are raw per-seed data — rerunning the matching `plot_*.py` redraws the figure
without retraining anything.

`dev/` holds everything from earlier checkpoints (ckpt1–ckpt5) and broader exploratory sweeps that
aren't part of the final report. Not deleted, just not part of the current story — see `cmc/dev/`,
`scripts/dev/`, `tests/dev/` for the matching code. Original paths before the cleanup are in the git
history (first commit).
