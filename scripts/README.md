# Scripts

One script per experiment:

- `run_e1_curriculum.py` / `plot_e1_curriculum.py` — curriculum vs no-curriculum
- `run_e2_reasons.py` — why System 2 is still called (no_match / multi_match / below_threshold)
- `run_e3_ablation.py` — one-at-a-time ablations of the full mechanism
- `run_e4_teacher_quality.py` — BFS vs EHC as System 2
- `run_e5_scaling.py` / `plot_e5_scaling.py` — train at n=4, test on bigger held-out sets
- `run_gripper_table.py` — generalization to Gripper (E6)
- `run_sweep.py` — the wider sweep E2/E3's numbers were cross-checked against

Each `run_*.py` writes its data to `results/`. `dev/` contains temporary work.
