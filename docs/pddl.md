# PDDL pipeline

Domains and problems are PDDL files; System 2 is a standard planner library (pyperplan). Nothing outside
the problem *generators* knows about a particular domain.

## Layout

- `domains/<name>/domain.pddl`, `example_problem.pddl`: `blocksworld` (the one used so far) and a typed
  `gripper` (used to check the layer is domain-independent).
- `cmc/pddl.py`: reads files with pyperplan's parser. `PddlDomain` holds the lifted operator model in the
  dict format the learners use, plus `apply` / `applicable_actions` / `goal_holds`. `PddlProblem` holds
  objects, initial state and goal. Typing is compiled into unary static predicates `type:T`, so learners
  need no notion of types.
- `cmc/system2.py`: System 2 = pyperplan, `ehc` (enforced hill-climbing + hFF) or `bfs`. Cost is counted
  inside the library's own loops (`expansions`, `evals`; `work` is their sum). With `bfs`, `optimal(action)`
  is a lazy judge ("does this action start a shortest plan?") that a learner may call in a clash.
- `cmc/experiment.py`: train / frozen-test protocol and audit metrics (exact distance is used only to audit).
- `cmc/contrast_induce.py`: the domain-independent learner (takes `operators` and `apply_fn`).
- `cmc/domain.py`: the default operator model, now compiled from `domains/blocksworld/domain.pddl`
  instead of a hand-written dict; the checkpoint 1-3 code keeps working through it.

## Running

    python scripts/make_problems.py --out data/problems/bw_n4_s0          # blocksworld generator -> .pddl files
    python scripts/run_pddl.py --domain domains/blocksworld/domain.pddl \
        --train data/problems/bw_n4_s0/train --test data/problems/bw_n4_s0/test --s2 bfs
    python scripts/run_ckpt6.py --s2 bfs          # the full learner comparison (5 seeds)

Train files run in filename order (that is the curriculum). Any other STRIPS(+typing) domain works the
same way once its problems are in a folder.

## Random-walk curriculum (option)

`cmc/random_walks.py` builds training problems without hand-built phases (Fern, Yoon, Givan 2004): scramble a template
problem's initial state, walk n random applicable actions, and take what is true at the end (restricted to the
template goal's predicates, optionally a random fraction of it) as the goal. Such problems are always solvable.
`WalkTraining` adapts n to how much of the work System 1 has been doing. Use it with `--walk` in `run_standard.py` or
`run_bundle.py`, or pass a `WalkTraining` to `evaluate` in place of a list of problems.

## Second domain

Gripper runs through the same layer and learner; see `docs/gripper.md`.

## Limits

STRIPS with `:typing` only (what pyperplan parses): no `:constants`, negative preconditions, conditional
effects or numeric fluents. The checkpoint-3 baseline learners (`cmc/induce.py`) are blocksworld-only
because they read the default domain's operators.
