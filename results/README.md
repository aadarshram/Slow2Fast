# Results

Track experiments:


| Report section                      | Script                                                     | Result file                                   |
| ----------------------------------- | ---------------------------------------------------------- | --------------------------------------------- |
| E1 (curriculum vs no-curriculum)    | `scripts/run_e1_curriculum.py` + `plot_e1_curriculum.py`   | `e1_curriculum.json` / `.pdf`                 |
| E2 (why System 2 is still called)   | `scripts/run_e2_reasons.py`                                | `e2_reasons.json`                             |
| E3 (ablations)                      | `scripts/run_e3_ablation.py`                               | `e3_ablation.json`                            |
| E4 (BFS vs EHC teacher)             | `scripts/run_e4_teacher_quality.py`                        | `e4_teacher_quality.json`                     |
| E5 (scaling to larger n)            | `scripts/run_e5_scaling.py` + `plot_e5_scaling.py`         | `e5_scaling.json` / `.pdf`                    |
| E6 (Gripper)                        | `scripts/run_gripper_table.py`                             | `e6_gripper_bfs.txt`, `e6_gripper_ehc.txt`    |
| future-work line (Barman/Logistics) | `scripts/dev/run_bundle.py`, `scripts/dev/run_standard.py` | `standard_ehc.txt`, `outcomes_barman_bfs.txt` |


All `*.json` files above are raw per-seed data -  rerunning the matching `plot_*.py` redraws the figure
without retraining anything.

`dev/` holds everything from earlier checkpoints and broader exploratory sweeps.