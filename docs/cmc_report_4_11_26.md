# Thinking Fast and Slow : Progress Report

Aadarsh Ramachandran (EE23B001); Aditya Girish (EP23B048)

Since the previous report,  we were adapting PG3-style policy learning in blocksworld: a decision list tried first, a planner filling gaps, and rules built from planning traces in a largely batch way. Several design tensions were already visible (continual vs batch update; matching on the final goal; no clear stop on list size). These were not issues for PG3 since they leverage a planner to learn a general policy while we want to demonstrate "learning a policy from experience" solely from previously seen planning traces.

Since then, I revisited Kahnman's works to ensure we commit strictly to his accounts and systematically tried developing over three checkpoints. System 1 is a decision list of lifted cue-action rules and what matters is can we learn such list so that overtime in random tasks, mostly, system 1 is called than system 2. Current standing: I was able to design a currculum approach of sequence of types of tasks which help learns different rules (this is oracle knowledge). Using this and then only random tasks I was able to show it learnt enough rules, mostly system 1 executes. **But the question we are stuck on is:  Balance between general and specific rules (most system 2 calls left were because of these trade-off reasons and I can't find a proper balance between both extremes.)**

---

### **Detailed Report with Doubts for Discussion**

## Kahnman's background

Skilled intuition is recognition built by practice with feedback in a high-validity setting (Kahneman and Klein, 2009; Kahneman, 2011). It is recognition and no search inside cues. (Simon, 1992). Expertise is a collection of miniskills from different recognitions and need not be a policy that solves the whole task (Kahneman, 2011).

Rules I commit to:

1. A cue fires only after the same pattern has been confirmed twice (threshold - idea of practice).
2. Exactly one match may propose; several matches refuse. Kahnman's work says system 1 cannot resolve ambiguity so call system 2.
3. System 2 answers whenever recognition fails.
4. System 2 is satisficing not optimal: first plan that reaches the goal (Simon, 1955; Klein, 1989), instead of BFS I implemented it as enforced hill-climbing (Hoffmann and Nebel, 2001). One action is executed; recognition is offered the next state again.

## How a rule is found (triangle-table style)

When System 1 cannot uniquely propose, System 2 returns a plan trace. We execute the first action (after cutting loops; to ensure no infinite loopholes).  From the trace we learn rules.

Rule construction follows the spirit of triangle tables (Fikes, Hart, and Nilsson, 1972), also used in PG3’s “Induce Rule from Plans” (Yang et al., 2022):

- Roll the plan forward and find a **permanent goal atom**: a goal literal that becomes true at some step and stays true to the end. Prefer an atom that is an **add effect** of the taught action.
- Seed **state conditions** from the operator preconditions of that action (domain model).
- Seed **goal conditions** from that permanent atom and, in checkpoint 3, often from further goal literals of the problem.
- Lift object names to variables. A rule does not become System 1 until its confirmation count reaches the practice threshold.

So the cue is “situation + relevant goal fragment → this action,” induced from an executed deliberate plan, no search over hypothetical policies.

---

## Checkpoint 1 - one miniskill

**Question.** Can System 1 learn only `stack`, while the planner does every other step?

**Setup.** Towers from the table. Cue: holding `?x`, clear `?y`, goal `on(?x,?y)`. 

**Result.** After practice on a short tower, a taller tower with new names uses System 1 for every practiced `stack`; pickups executed by System 2.  Shows that a rule can be learnt and then used for similar problems.

**Limit.** Only `stack`. Next was to extend to multiple rules.

---



## Checkpoint 2 - hand library on a fixed curriculum

**Question.** On a narrow family of tasks, can a small hand-written library take over completely on frozen tasks with new names?

**Setup.** Five cues: `pickup-base`, `pickup-next`, `stack`, `unstack`, `putdown`. Experience introduce one new cue at a time as practice. Finally evaluate on random tasks.

**Result.** Learning moves from all System 2 → shared steps → fully System 1. Frozen copies with new names are entirely System 1. Confirms recognition + practice works on this family when the rules are given. (ie, there exists rules which can support the system 1 takes over system 2 claim.)

**Limit.** I defined rules here. Next is to learn them.

---

## Checkpoint 3 - induce rules on a generator

**Question.** Does the same loop still work when rules are **induced** from traces on generated multi-tower problems (no hand designed rules except for the curriculum)?

**Setup.** Curriculum: single tower → multi-tower → partial stacks → 100 random tasks (`n≤4` blocks). Induce online from System 2 experience. Test on 100 random tasks with freeze rules.

**Train result** (`seed=0`, practice 2):


| Phase       | Tasks   | System 1 share |
| ----------- | ------- | -------------- |
| single      | 10      | 0.694          |
| multi       | 9       | 0.875          |
| partial     | 6       | 0.833          |
| random      | 100     | 0.778          |
| **overall** | **125** | **0.779**      |


All tasks reached the goal. Library size: **16** rules.

**Frozen test (induce only):** System 1 share ≈ **0.704**. Among System 2 failures, **multi_match** dominated (~77); **no_match** was rare.

### What that showed about specialization

We often called System 2 because **several** cues matched and we refuse ties. We had no rewrite that would differentiate those rules.

We also grew **narrow** rules that never reached the practice threshold, so they never fired. Useless over-specific rules sat beside over-general ones that needed a differentiator.

---

## Trying PG3-style add / delete (experiment only)

PG3 learns generalized policies with operators including **Add Condition** and **Delete Condition** (Yang et al., 2022). Their overall recipe (search over policies, planner rollouts, replace the planner) is not ours. We borrowed only the local edits:

- **Add:** attach a state/goal literal → specialize.
- **Delete:** drop a literal (not true action preconditions) → generalize.

We applied them greedily after each lesson, accepting an edit only if it stayed consistent on the **full trace history**.  That does not fit Kahnman but just tried it out.

### Add only


|                              | Induce only | Add only  |
| ---------------------------- | ----------- | --------- |
| System 1 share (frozen test) | ~0.704      | **0.731** |
| Rules                        | 16          | 25        |
| multi_match                  | ~77         | **10**    |
| no_match                     | ~0          | **68**    |


Add condition killed clashes by attaching literals from the current scene/goal. **Multi_match fell; no_match rose.** System 2 was called for silence instead of ambiguity. 

### Add + delete (including goal literals)


|                | Add only | Add + delete |
| -------------- | -------- | ------------ |
| System 1 share | 0.731    | **0.574**    |
| Rules          | 25       | **45**       |
| multi_match    | 10       | 11           |
| no_match       | 68       | **93**       |


Delete often stripped **goal** cues. Rules got broadened and it grew brittle. Number of rules also increased while system 1 share reduced. 

---

## Summary table (frozen test, 100 random)


| Setup             | s1 share | Rules | Main S2 mode     |
| ----------------- | -------- | ----- | ---------------- |
| Ckpt3 induce only | ~0.704   | 16    | multi_match      |
| + add condition   | 0.731    | 25    | no_match         |
| + add and delete  | 0.574    | 45    | no_match (worse) |


Add/delete mostly **relabel** System 2 (clash ↔ silence). They do not give a Kahneman-faithful account of how cues should sharpen or loosen.

---

## Open Questions

1. **Update without full-history search.** What revision rule stays local to the current lesson (and light feedback), aligned with recognition-with-practice, rather than PG3-style consistency over all traces?
2. **Criterion for the specialization–generalization tradeoff.** When should we narrow a cue, broaden it, or leave the clash/silence to System 2? How to ensure balance?
3. **On multi_match, if we executed the first match instead of refusing,** execution gives feedback on that action’s progress, but little direct signal about the other matching rules. Is first-match + some progress/S2-agreement signal acceptable, or must unique-or-refuse stay? (Kahnman says refuse I think.)

## References

Fikes, R. E., Hart, P. E., & Nilsson, N. J. (1972). Learning and executing generalized robot plans. *Artificial Intelligence, 3*(1–4), 251–288.

Hoffmann, J., & Nebel, B. (2001). The FF planning system: Fast plan generation through heuristic search. *Journal of Artificial Intelligence Research, 14*, 253–302.

Kahneman, D. (2011). *Thinking, fast and slow*. Farrar, Straus and Giroux.

Kahneman, D., & Klein, G. (2009). Conditions for intuitive expertise: A failure to disagree. *American Psychologist, 64*(6), 515–526.

Klein, G. A. (1989). Recognition-primed decisions. In W. B. Rouse (Ed.), *Advances in man-machine systems research* (Vol. 5, pp. 47–92). JAI Press.

Simon, H. A. (1955). A behavioral model of rational choice. *The Quarterly Journal of Economics, 69*(1), 99–118.

Simon, H. A. (1992). What is an “explanation” of behavior? *Psychological Science, 3*(3), 150–161.

Stanovich, K. E., & West, R. F. (2000). Individual differences in reasoning: Implications for the rationality debate? *Behavioral and Brain Sciences, 23*(5), 645–665.

Yang, R., Silver, T., Curtis, A., Lozano-Pérez, T., & Kaelbling, L. P. (2022). PG3: Policy-guided planning for generalized policy generation. *Proceedings of the Thirty-First International Joint Conference on Artificial Intelligence*, 4684–4690.