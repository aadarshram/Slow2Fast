# Scripts

One script per experiment in the report:

- `run_e1_curriculum.py` / `plot_e1_curriculum.py` — curriculum vs no-curriculum
- `run_e2_reasons.py` — why System 2 is still called (no_match / multi_match / below_threshold)
- `run_e4_ablation.py` — one-at-a-time ablations of the full mechanism
- `run_e6_teacher_quality.py` — BFS vs EHC as System 2
- `run_e8_scaling.py` / `plot_e8_scaling.py` — train at n=4, test on bigger held-out sets
- `run_gripper_table.py` — generalization to Gripper (E7)
- `run_ckpt6.py` — the wider sweep E2/E4's numbers were cross-checked against

Each `run_*.py` writes its data to `results/`; see `results/README.md` for which file goes with
which section. `dev/` is everything from earlier checkpoints that isn't part of the final report.
