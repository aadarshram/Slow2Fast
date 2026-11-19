# Gripper

Second domain, run through the same PDDL layer and the same learner as blocksworld. Only the problem
generator (`cmc/gripper_problems.py`) is Gripper-specific. Domain file: `domains/gripper/domain.pddl`
(typed: room, ball, gripper; actions move, pick, drop).

Run: `python scripts/run_gripper.py --stage {1,2,3} [--ties] [--rules]`,
`python scripts/run_gripper_table.py --s2 {bfs,ehc} --ood 30` (5 seeds, ablations, larger problems),
or from files: `scripts/make_gripper_problems.py` then `scripts/run_pddl.py --domain domains/gripper/domain.pddl ...`.

## Stages

1. **A few rules.** One ball, two rooms, two grippers (plan: pick, move, drop). 6 training problems, 30 fresh
   ones with new names: three rules, S1 share 1.000, precision 1.000, no System 2 calls.
2. **Deliberate curriculum.** single, fetch (robot in the wrong room), two balls (shared / split goals), balls
   already home, three rooms, one and three grippers. 24 training problems. Fresh curriculum-shaped problems:
   S1 share 0.942 (0.971 with ties); random problems: 0.888 (0.927 with ties). Four rules.
3. **General.** Curriculum plus 100 random problems (2-4 rooms, 1-4 balls, 1-2 grippers, goals on a random subset
   of balls), tested on a frozen random holdout and on larger problems (up to 4 rooms, 5 balls, 3 grippers).

## Stage 3 results (5 seeds; held-out seeds 100-104 in brackets)

BFS as System 2, test S1 share / S2 cost as % of pure System 2:

| Setting | Test S1 share | S2 cost | Larger problems |
|---|---|---|---|
| original settings (as for blocksworld) | 0.667 (0.678) | 68% | 0.532 |
| + symmetry | 0.807 (0.815) | 52% | 0.685 |
| + symmetry + full cover | 0.951 (0.949) | 18% | 0.862 |
| + symmetry + full cover + ties | **0.976 (0.978)** | 10% | 0.915 (0.952) |

With enforced hill-climbing: 0.674, 0.844, 0.968 and 0.974 (held-out 0.951 for the last two); larger problems
0.909. Ties add little there because no judge exists. Ablations (with ties): without the deferral link 0.838
(EHC 0.754); without symmetry 0.976 under BFS but 0.803 under EHC; sat/unsat features, merge and negated
literals make no meaningful difference. All problems are solved in every setting; S1 precision 0.97-1.00.

The learned policy is small: `pick` (ball with a goal), `drop` (goal is here), and `move` as "to the goal room of
a carried ball" or "to the room of a ball that must be moved", with `move` yielding to `pick`/`drop`.

## What was needed beyond blocksworld, and why

- **Symmetry.** `pick(b, r, left)` and `pick(b, r, right)` are different actions with identical value, so
  unique-or-refuse could never fire. Actions related by an object swap that leaves state and goal unchanged
  are treated as one choice (domain-independent check).
- **Full cover.** Forking a rule into children that cover only some of its positives silently dropped the rest
  and shredded the basic delivery rule into fragments. Now a rule forks only if the children keep all its
  positives; otherwise it stays and defers. Neutral on blocksworld under BFS, better under EHC.
- **Ties (opt-in).** Many Gripper decisions are interchangeable (which ball first). With a judge (BFS), rules
  that were repeatedly seen to propose equally acceptable actions together are no longer refused. This relaxes
  strict unique-or-refuse: it needs a defensible argument in the report.
- **Wider refinement vocabulary.** A literal may introduce up to two fresh objects (e.g. `carry(?n0,?n1)`).
  It did not help by itself; kept because it is needed to state the delivery rule.
- Tried and removed: requiring several positives before specialising a rule (made things worse).

## Limits

Gripper's compact policy was found with a hand-built curriculum (oracle, as for blocksworld). The development
seeds were used to find the changes above; the held-out seeds agree. Not tested: more than 4 rooms/5 balls,
partial observability, or other domains. Problems are solved by System 2 whenever System 1 declines, so
"solved" is not evidence that the rules alone solve the domain.
