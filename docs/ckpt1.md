# Checkpoint 1

This is the first runnable slice of the System 1 / System 2 planner in `docs/tfs.md`. The domain is given. System 1 may learn only `stack`. A planner does every other step, and it remains in the loop after `stack` is practiced.

What “works” means: after practice, a new tower with different block names is finished; every `stack` whose cue has succeeded twice is taken by System 1; every `pickup` is taken by the planner; a cue that matches two groundings does not choose one of them; a rule that has succeeded only once does not fire.

## Task

Blocks start on the table, clear, with the hand empty. The goal is one tower, written as `on` atoms. The top block is the first name. `tower(["a", "b", "c"])` means `a` on `b` on `c`, and `c` stays on the table.

The operators are the ordinary four.

`pickup(?x)` requires `clear(?x)`, `ontable(?x)`, and `handempty`. It adds `holding(?x)` and removes those three.

`putdown(?x)` requires `holding(?x)`. It adds `ontable(?x)`, `clear(?x)`, and `handempty`, and removes `holding(?x)`.

`stack(?x, ?y)` requires `holding(?x)` and `clear(?y)`, with `?x` and `?y` distinct. It adds `on(?x, ?y)`, `clear(?x)`, and `handempty`, and removes `holding(?x)` and `clear(?y)`.

`unstack(?x, ?y)` requires `on(?x, ?y)`, `clear(?x)`, and `handempty`. It adds `holding(?x)` and `clear(?y)`, and removes `on(?x, ?y)`, `clear(?x)`, and `handempty`.

System 1 is not allowed to learn `pickup`, `putdown`, or `unstack`. Those steps are System 2 even after `stack` is practiced.

## System 2

System 2 is breadth-first search from the current state to a state that contains the goal. It does not read the rule set. Shorter plans win. The action order inside a state is fixed, so a given problem has one returned plan: `unstack`, `pickup`, `putdown`, `stack`, and blocks in sorted name order.

The search is the planner for this checkpoint. It is not Fast Downward. The problems are small, and the tests need a planner that ships with the code. The rules never change the search.

If the goal is already true, the plan is empty. If no plan exists inside a depth bound of `8` times the number of blocks, the search returns no plan.

## System 1

A rule is one miniskill.

- Action name `stack`.
- Parameters `?x`, `?y`.
- State cue: the preconditions of `stack` that held, `holding(?x)` and `clear(?y)`.
- Goal cue: the goal atom the action adds, `on(?x, ?y)`.
- Expected effect: the add and delete lists of `stack`.
- A confirmation count, starting at 0.
- A retired bit.
- The pre-states of the successful uses, kept so a later failure can look for one extra literal. These records are not a rollout. They are states that were already executed.

A grounding substitutes blocks for `?x` and `?y`. It matches when every state literal is in the current state and every goal literal is in the goal. A practiced rule proposes an action only when exactly one grounding matches, across the whole set of practiced rules. Two groundings, or two rules, produce no proposal. Nothing is chosen by object name.

A rule with fewer than 2 confirmations is not practiced and proposes nothing. The threshold is a parameter of the run, and the checkpoint uses 2.

## One step

The episode starts from the initial state and remembers every state it has been in.

If the goal atoms are in the state, stop.

Otherwise ask the practiced rules for a proposal. A proposal whose successor state is already in the episode is discarded. That is the repeated-state interrupt: System 1 may not walk back into a state it has already produced.

If a proposal remains, apply it and compare the successor with the effect of `stack`.

- The effect holds. Count a System 1 success. During training, add one confirmation and store the pre-state. During a frozen test, change nothing in the library.
- The effect does not hold. Count a System 1 failure. Call the revision below. The bad action has already happened. The next step continues from the observed state.

If there is no proposal, System 2 returns a plan from the current state and the episode executes the first action of that plan. Count a System 2 step. During training, a `stack` whose effect holds is a lesson. Any other planner action writes nothing.

The step bound is `8` times the number of blocks. Hitting it, or a missing plan, is a failed episode.

## How a lesson is written

Only a planner `stack` whose effect held may create or rewrite a rule. A System 1 success only confirms.

Look for a non-retired rule whose cue matches this `stack` under the binding `{?x = the held block, ?y = the support}`. If one exists, add one confirmation and store the pre-state. If none exists, create that cue with one confirmation and store the pre-state. A retired rule with the same cue is not recreated.

Two planner stacks of this same lifted cue are enough. In a tower of three or more blocks the first tower contains two `stack` steps, so the rule becomes practiced at the end of that tower. Both of those steps are still System 2, because the count reaches 2 only after the second effect is observed. A tower of two blocks has one `stack`, so the rule is practiced only after a second tower, and it fires on the third.

## Revision

Revision runs on the pre-state of a fire whose effect did not hold. Lift atoms whose arguments are among `?x` and `?y`, plus atoms with no arguments. Keep a literal that is true under every stored successful binding and false under the failed binding, and that is not already in the cue.

One such literal is added to the state cue. The confirmation count is left as it is. Zero such literals, or more than one, retires the rule. No second `stack` rule is appended.

## What is frozen at test time

Training runs episodes with updates on, one tower after another, on the same library. The test episode uses that library with updates off. Confirmations, retirement, and new rules stay as they were at the end of training.

## Numbers

For each episode record:

- steps whose practiced rule fired and whose effect held
- steps whose practiced rule fired and whose effect did not hold
- steps taken by the planner
- whether the goal held at the end
- the confirmation count of each live rule

Whole-task success is recorded and is not the result that matters. The planner can finish a tower by itself.

## Checks

A typical run trains on `a` on `b` on `c`, then solves `w` on `x` on `y` on `z` with the library frozen. The training episode is four planner steps. The rule ends at 2 confirmations. The test episode is pickup, stack, pickup, stack, pickup, stack, and the three stacks are System 1.

An edge run uses two-block towers. After one tower the only `stack` rule has 1 confirmation and must not fire. The second tower’s `stack` is still the planner and raises the count to 2. The third tower’s `stack` is System 1.

A bad input is a goal `on(a, b)` and `on(b, a)`. The search returns no plan, the episode stops, and the goal is not marked reached. A goal that already holds produces an empty episode. A practiced rule presented with two legal supports proposes nothing.

A separate revision check feeds successful pre-states in which the support is on the table, then a failure in which it is not. The rule gains `ontable(?y)`. A failure whose pre-state matches the successes on every such literal retires the rule instead.

## Known limit

The cue can match before the support is in its final place. Holding `a`, with `b` clear on the table, and both `on(a, b)` and `on(b, c)` in the goal, is a unique `stack(a, b)`. The effect of that stack holds, so the fire counts as a success even though `b` still has to move. The repeated-state interrupt stops the resulting undo-and-restack loop, and the planner then puts `a` down and builds the tower from the base. The training and test towers in this checkpoint start with every block on the table, and the shortest plan never enters that state. The checkpoint does not claim the cue is right for a hand that already holds the wrong block.

Scenes that start with a tower to be taken apart are also outside the claim. `unstack` stays with the planner. A `stack` whose cue really holds may still fire.

## How to run

From `cmc_project`:

```bash
python -m unittest tests/test_ckpt1.py
python scripts/run_ckpt1.py
```

The script trains on one three-block tower, tests on one four-block tower, and writes `results/ckpt1.txt`.
