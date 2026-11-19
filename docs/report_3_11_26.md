# Issue of specialization vs generalization

Date: 3 Nov 2026

## What we had through checkpoint 3

Checkpoint 3 asked whether the System 1 / System 2 split still works when cue–action rules are **induced** from planner traces on a generated multi-tower curriculum, instead of hand-written cues on a fixed lesson list.

System 2 is a satisficing planner. System 1 is a library of lifted rules (state conditions, goal conditions, one action). A rule may fire only after a practice threshold (2) and only when **exactly one** grounding matches. Several matches mean refuse, not a lexicographic pick. The planner stays in the loop. The headline metric is System 1’s share of steps.

Induction seeds each new rule from the missed action: operator preconditions for state, and often a large slice of the problem’s complete goal. Later traces can repair over-fat goals. There was **no** operator that rewrote rules to separate colliding cues.

### Results (documented ckpt3)

On train (`n=4`, `practice=2`, `seed=0`, curriculum ending in 100 random tasks): every task reached the goal. Overall System 1 share was about **0.779** (random tail about **0.778**). The library ended with **16** rules.

On a later frozen test of 100 random tasks with that style of library (induce only, no add/delete): System 1 share was about **0.704**, with **multi_match** dominant among System 2 reasons (on the order of **77**), and almost no **no_match**.

So recognition often failed because **too many** cues fit, not because **none** fit.

## Two failure modes in that library

**Too general.** Many System 2 steps fired because several practiced rules (or several groundings) matched the same situation. We had no mechanism that rewrote those rules so they would differentiate. Unique-or-refuse correctly handed control to System 2, but the library did not learn from the clash beyond storing another trace or inducing yet another overlapping rule.

**Too specific.** Other rules described narrow scenes or goal fragments. They never reached the practice threshold, so they never fired as System 1. They sat in the library as dead weight: specialized enough to be rare, not practiced enough to be used.

The open issue is the classic tradeoff: cues broad enough to recur, sharp enough to be unique.

## Ideas from planning: PG3 add / delete condition

We looked at generalized policy learning in planning, especially PG3 (Yang, Silver et al., 2022). Their setting is not the same as ours. They search over lifted decision-list policies and score candidates with policy-guided planning; the aim is a policy that can replace the planner. We keep the planner and care about Kahneman-style recognition share.

Still, their local edit operators were useful as ideas:

- **Add condition.** Attach an extra state or goal literal to a rule so it matches fewer situations (specialize).
- **Delete condition.** Drop a literal from state or goal conditions so the rule matches more situations (generalize). Literals that are true action preconditions are not deleted.

In our code we tried a **local** version after each System 2 lesson: if the current problem still shows a clash, greedily add (or, in a later trial, also delete) literals, accepting an edit only if it stays consistent on the **full stored trace history**.

That already sits poorly with Kahneman. Skilled intuition is recognition in the present case with feedback over practice. It is not re-checking every past episode and running long repeated trials until the archive is coherent. We tried it anyway as an engineering experiment, not as a cognitive claim.

## Experiment: add condition only

Delete was disabled. After each lesson, only add condition ran.

Frozen test (100 random, same seed):

| | Induce only (ckpt3-style) | Add only |
| --- | ---: | ---: |
| System 1 share | ~0.704 | **0.731** |
| Rules | 16 | 25 |
| multi_match | ~77 | **10** |
| no_match | ~0 | **68** |

Add condition did what it is designed to do: when two rules collided on a lesson, it piled on literals from that scene or goal until the clash died. **Multi_match fell sharply.**

The cost showed up as **no_match**. The extra literals were often accidental differentiators for *today’s* problem. On a later random layout those lits failed, so nothing fired. System 2 was called for silence instead of ambiguity. Specialization moved the mass from multi_match to no_match; System 1 share rose only a little.

## Experiment: add and delete (including goal conditions)

We then enabled delete condition in the standard PG3 sense, including dropping **goal** literals, with the same full-history acceptance tests. No transfer gate.

Frozen test:

| | Add only | Add + delete |
| --- | ---: | ---: |
| System 1 share | 0.731 | **0.574** |
| Rules | 25 | **45** |
| multi_match | 10 | 11 |
| no_match | 68 | **93** |
| below_threshold | 2 | 20 |

Delete was meant to undo over-specialization. In practice it often stripped **goal** cues that had made pickup/stack goal-sensitive. Rules became broad again (empty or thin goals), clashes returned, and add condition answered by gluing on brittle **state** literals. Some combinations were nearly useless on later tasks (high confirmations, rare or impossible match). The library grew; **no_match rose further**; System 1 share fell below plain ckpt3.

So delete did not resolve the tradeoff. It amplified oscillate-and-patch behavior under full-history repair.

## Where this leaves us

Add and delete are blunt controls on specificity. In our stream they mostly **relabel** System 2: clash versus silence. They depend on full-history search and repeated trials, which we do not want to treat as Kahneman-faithful.

**Open questions**

1. What update rule fits recognition-with-feedback: local to the current lesson (and maybe a light notion of recent failure), without optimizing consistency over the entire trace archive?

2. More importantly, **what is the criterion for the specialization–generalization tradeoff?** When should a cue be narrowed, when broadened, and when left alone so System 2 simply handles the case? Accuracy on frozen random tasks, multi_match vs no_match balance, rule count, practice mass on a small core of cues, or something else?

We need a principle for that criterion before grafting more PG3-style edits onto the loop.
