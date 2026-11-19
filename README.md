# cmc_project

A System 1 / System 2 framework for planning, following Kahneman and Klein's account of
skilled intuition. A deliberate planner (System 2) solves tasks by search; a library of
lifted cue-action rules (System 1) is induced from its traces and takes over an increasing
share of decisions, with the planner always kept as a fallback for whatever the library
cannot handle unambiguously.

## Summary

System 1 is a set of lifted rules, each a state/goal cue paired with one action. A rule may
only fire once it has been confirmed correct twice (a practice threshold), and only when
exactly one rule's grounding matches — two matches mean refuse, not guess. Whenever System 1
cannot decide, System 2 (a PDDL planner, pyperplan under the hood) solves the step, and that
solved step becomes a lesson: either a new rule is induced from the trace, or an existing rule
is specialized (if it just proposed the wrong thing) or generalized (if nothing fired but it
was close). The project asks whether this loop lets System 1 take over most decisions on
unseen tasks, whether that depends on a staged curriculum, which parts of the update rule
actually matter, whether an optimal planner is required to teach it, and whether it transfers
to bigger problems and to a second domain. `docs/` has the development write-ups from along
the way; the final report has the full account.

## Repo structure

```
cmc/              core library — the domain model, the planner, and the System 1 mechanism
  contrast_induce.py   the full mechanism (rule representation, specialize/generalize)
  system2.py           System 2 (pyperplan EHC/BFS) and the control loop
  domain.py, pddl.py   PDDL domain model and parsing
  blocksworld.py, generate.py, gripper_problems.py   problem generators
  experiment.py        train/test harness used by every experiment script
  baselines.py, induce.py   comparison baselines (induction without refinement)
  dev/              earlier checkpoints' code, kept for reference, not part of the final report

scripts/          one script per reported experiment (see scripts/README.md)
  dev/              earlier checkpoints' scripts and broader exploratory sweeps

results/          the data and figures each script produces (see results/README.md)
  dev/              results from earlier checkpoints, grouped as dev/ckpt1/ .. dev/ckpt6/

domains/          PDDL domain files (blocksworld, gripper, and others tried along the way)
docs/             development notes and progress reports, written as the project went
tests/            unit tests for the active code; tests/dev/ covers the archived code
```

## Results, briefly

All numbers are System 1's share of decisions on held-out tasks, mean over 5 seeds, unless
stated otherwise. Full detail is in the report.

- **Headline (E1)**: the full mechanism reaches ~0.96 share on held-out blocksworld tasks,
  whether trained on a staged curriculum or on unordered practice of the same size — the
  curriculum turned out not to matter here.
- **Why System 2 is still needed (E2)**: without the refinement step, System 2 is called
  mostly because rules collide (0.70 share, ~104 collisions per 100 tasks); the full
  mechanism cuts that to ~5 collisions and reaches 0.96 share.
- **Which parts of the mechanism matter (E4)**: resolving a collision by deferring rather
  than forcing a bad edit, and requiring repeated evidence before specializing a rule, both
  matter a lot; a few other components barely move the numbers in blocksworld.
- **Does the teacher need to be optimal (E6)**: a satisficing planner (EHC) teaches about as
  well as an optimal one (BFS) — close coverage, close precision, close path-length overhead.
- **Does it transfer to bigger problems (E8)**: a library trained at 4 blocks still reaches
  0.82 share at 8 blocks — coverage declines gradually, not sharply, as size grows.
- **Does it transfer to a different domain (E7)**: the same mechanism, unmodified, reaches
  0.97 share in Gripper.

## How to run

```bash
conda env create -f environment.yaml
conda activate cmc_project
pip install -e .
```

Each experiment has one script in `scripts/` that writes its result file to `results/`, e.g.:

```bash
python scripts/run_e1_curriculum.py
python scripts/plot_e1_curriculum.py
```

See `scripts/README.md` for the full list and `results/README.md` for which file belongs to
which section of the report. Run the test suite with:

```bash
python -m pytest tests/ --ignore=tests/dev
```

## Acknowledgements

Built on [pyperplan](https://github.com/aibasel/pyperplan) for PDDL parsing and search.
Domain files are the standard IPC Blocksworld and Gripper benchmarks. Project for a cognition
course, by Aadarsh Ramachandran (EE23B001) and Aditya Girish (EP23B048).
