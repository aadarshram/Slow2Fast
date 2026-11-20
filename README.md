# From Slow Planning to Fast Decisions: A Dual-Process Architecture for Learning Planning Policies

A System 1 / System 2 framework for planning, following Kahneman and Klein's account of
skilled intuition. A deliberate planner (System 2) solves tasks by search; a library of
lifted cue-action rules (System 1) is induced from its traces and takes over an increasing
share of decisions, with the planner kept as a fallback.

## Summary

System 1 is a set of lifted rules, each a state/goal cue paired with one action. A rule may
only fire once it has been confirmed correct twice (a practice threshold), and only when
exactly one rule's grounding matches. Whenever System 1
cannot decide, System 2 (a PDDL planner) solves the step, and that
solved step becomes a lesson: either a new rule is induced from the trace, or an existing rule
is specialized (if it just proposed the wrong thing) or generalized (if nothing fired but it
was close). We ask whether this loop lets System 1 take over most decisions on
unseen tasks, whether that depends on a staged curriculum, which parts of the update rule
actually matter, whether an optimal planner is required to teach it, and whether it transfers
to bigger problems and to a second domain.

## Repo structure

```
slow2fast/              core library — the domain model, the planner, and the System 1 mechanism
  contrast_induce.py   the full mechanism (rule representation, specialize/generalize)
  system2.py           System 2 (pyperplan EHC/BFS) and the control loop
  domain.py, pddl.py   PDDL domain model and parsing
  blocksworld.py, generate.py, gripper_problems.py   problem generators
  experiment.py        train/test harness used by every experiment script
  baselines.py, induce.py   comparison baselines (induction without refinement)
  dev/              temporary work with early and new experiments.

scripts/          one script per reported experiment (see scripts/README.md)
  dev/              temporary work with early and new experiments.
results/          the data and figures each script produces (see results/README.md)
  dev/              temporary work with early and new experiments.

domains/          PDDL domain files (blocksworld, gripper, and others tried along the way)
docs/             dev/- development notes; final project report
tests/            unit tests for the active code; tests/dev/ for temporary work
```



## How to run

```bash
conda env create -f environment.yaml
conda activate slow2fast
pip install -e .
```

Each experiment has one script in `scripts/` that writes its result file to `results/`, e.g.:

```bash
python scripts/run_e1_curriculum.py
python scripts/plot_e1_curriculum.py
```

See `scripts/README.md` for the full list and `results/README.md`. Run the test suite with:

```bash
python -m pytest tests/ --ignore=tests/dev
```



## Acknowledgements

This work is part of course project for the course CS6251: Computational Models of Cognition by Aadarsh Ramachandran (EE23B001) and Aditya Girish (EP23B048), Indian Institute of Technology Madras.