# Thinking Fast and Slow

This note records the literature pass and the design decisions for a System 1 / System 2 planner. System 2 is classical search on a known PDDL domain. System 1 is a set of lifted cue–action rules, in the form used by PG3 (Yang et al., 2022), restricted by Kahneman’s account of skilled intuition. The last section is the first checkpoint: a blocksworld slice that is specified enough to implement.

The domain is given. Learning a domain, as in LODGE (Kienle et al., 2025), is a separate problem and is not part of this checkpoint.

## The target

The competence we want is the same kind of object PG3 learns, on the part of the domain experience has covered, with the planner kept for the rest.

A lifted rule takes the current state and the final goal and names one ground action. On a scene the rule covers, that action is the one a planner would have taken. The same rule applies to a similar scene with different objects. “Over time System 1 is used mostly” is that coverage stated as a fraction of a stream of tasks. PG3 states it as a fraction of a domain and drives the fraction to one by training until the list can replace the planner.

Experience is our training set. A task arrives, the current rules either handle the step or the planner does, and that executed trace is the lesson. PG3 chooses a training set in advance and searches over candidate lists. The policy at the end of both recipes is a lifted reactive list. The recipes differ in when the planner is allowed to act, and in what counts as done.

## Kahneman’s account

Kahneman (2011) takes the labels System 1 and System 2 from Stanovich and West (2000). System 1 is automatic, fast, and not under voluntary control. System 2 is slow, serial, and effortful. System 1 proposes impressions and intentions. System 2 endorses them, or overrides them when the situation is difficult. Kahneman’s formulation is that only System 2 follows an orderly series of rules and compares alternatives. System 2 can also reprogram what System 1 will later do without attention.

Skilled intuition, as Kahneman and Klein (2009) adopt it from Simon (1992), is recognition. A cue retrieves something stored, and that stored thing is the answer. They state two conditions. The environment must be high-validity: there are stable relations between identifiable cues and the outcomes of actions. The learner must have prolonged practice with feedback that is rapid and unequivocal. Subjective confidence is not a sign that the intuition is skilled. System 1 does not know when it does not know.

Kahneman and Klein (2009) also adopt Klein’s recognition-primed decision model (Klein, 1989; Klein et al., 1986). An experienced person recognizes a situation as a familiar case, and one plausible action comes to mind. That one action may be checked by mental simulation. If the simulation fails, the action is modified or dropped and another typical action is considered. Options are not generated as a set and compared. The criterion is satisficing (Simon, 1955): the first option that holds up, not the best option in a ranked list. Kahneman (2011) treats expertise in a complex domain as a large collection of miniskills, acquired slowly, rather than as one general procedure.

Two failure modes matter for a rule that fires on a partial match. Under “what you see is all there is,” System 1 builds a coherent story from the cues that are present and does not mark the cues that are absent (Kahneman, 2011). Attribute substitution answers a hard question by answering an easier one that the cues happen to suggest (Kahneman and Frederick, 2002). A goal atom that is present is an easier question than “is this the right next action in this tower.” Fractionation of skill is the related error of using a real skill outside the conditions in which it was practiced (Kahneman and Klein, 2009).

The 1982 simulation heuristic is a different claim and should not be mixed in. There, people judge an event as likely because a scenario is easy to imagine (Kahneman and Tversky, 1982). The simulation Kahneman accepts from Klein is a check of one proposed action, not a judgment of probability and not a search over many imagined policies.

Hogarth (2001) names the same preconditions, a regular world and a chance to learn it. Ericsson (2006) stresses deliberate practice. We use Kahneman and Klein (2009) as the operational statement: valid cues, repeated practice, fast unequivocal feedback, and a monitor that does not treat a feeling of familiarity as proof.

## What that account requires of a planner

**A miniskill is the stored unit.** Each System 1 item is a lifted cue, one action, and the effect that should follow. A single grounding proposes the action. Several rules, or several groundings of one rule, produce no action, and the planner is called. An ordered scan that takes the first applicable rule is rule-following, which Kahneman assigns to System 2. An arbitrary order on object names is a comparison pretending to be a recognition.

**Practice comes from executed feedback.** A rule is written from a trace that was actually carried out. The domain’s preconditions and effects may be used to read that trace. They may not be used to walk a candidate rule into a state that was never visited. One exposure stores a candidate. The candidate becomes System 1 only after the same cue has been followed by the expected effect on more than one occasion. Kahneman and Klein (2009) do not give the count. The checkpoint below sets it to 2 and treats that number as a reported parameter.

**The planner stays.** System 2 keeps the last word after skill exists. A test in which the rule list must finish the problem alone answers PG3’s question and drops Kahneman’s division of labor. The useful split is the one at execution time: follow a unique practiced rule while it matches, and call the planner when it does not.

**Surprise is the interrupt.** Klein’s experts carry expectations. In this setting the expectation is the effect of the action just taken. If the observed state lacks that effect, the planner is called and the rule that fired is revised. “The goal is not true yet” is true of every correct prefix, so it cannot be the interrupt. A repeated state is a second interrupt, because a rule that undoes its own progress would otherwise loop without ever failing a goal test.

**A contradicted rule is edited in place.** Adding a later rule leaves the old habit able to fire. Feedback that contradicts a fired rule adds one missing cue, or retires the rule. System 1 reads habits. An appended alternative that loses the match never corrects the habit.

**Generalization stays inside the practiced cues.** A taller tower of the same kind is the same skill when the same literals are present. A scene that requires taking a tower apart is a different task, even if some of the same literals match. That boundary is fractionation of skill (Kahneman and Klein, 2009). Lifting object names is the part of generalization the account supports. A guarantee that one list solves every larger instance is not.

**The numbers to report** are the fraction of steps on which a practiced rule fired and the expected effect arrived, and the fraction of fires whose effect did not arrive. The first is the growth of System 1. The second is the overconfident recognition the 2009 paper separates from skill. Whole-task success stays high whenever the planner is allowed to finish, so it does not make that separation.

## PG3

PG3 learns one lifted decision list for a PDDL domain (Yang et al., 2022). The hypothesis class is the first-order decision list (Mooney and Califf, 1995; Khardon, 1999; Levine and Humphreys, 2003). A rule has parameters, state preconditions, goal preconditions, and one action from the domain. Given a state and a goal, the first rule whose state literals hold and whose goal literals sit inside the goal fires. If several groundings match, PG3 takes the first under a fixed object order. The policy is partial: if no rule applies, it is undefined. Repeated firing is what produces looping behavior. The list has no numbers, no transitive closure, and no universal quantifiers (Yang et al., 2022). The authors note that the method is not tied to this hypothesis class.

Training has two searches. The outer search is greedy best-first search over decision lists, starting from an empty list, with a budget of 2500 expansions. The inner search is A* over states, using the additive heuristic (Bonet and Geffner, 2001). Ordinary actions cost 1. Wherever the current list applies, A* also follows it for up to 50 steps, and those steps cost 0. The score of a list is the number of actions in the resulting plan that differ from what the list would have named, or the maximum horizon if no plan is found. Scores across training problems are combined by a max. A small description-length penalty breaks ties.

The zero-cost steps are not a gift from the planner. They are the search treating “do what the list already says” as free, so a list that is right except for a few gaps ranks above a list that is wrong everywhere. Policy evaluation, which only counts problems the list solves by itself, gives a zero score to every list that has not finished a problem. Plan comparison, which scores agreement with an ordinary planner’s plan, punishes a good list whenever the planner found a different plan. PG3 is the score that avoids both of those failures (Yang et al., 2022). The theorems that make the score equal to the number of edits still required are proved for a tabular policy, with training problems equal to test problems. The paper states that they do not extend to lifted decision lists, because one edit of a lifted rule can change the action in every state. There is no convergence proof for the decision-list search. The empirical result is that, inside the expansion budget, every seed on six domains returned a list that solved the held-out problems. Blocks was not one of the domains.

New rules are proposed by search operators: add a rule that copies a domain action, delete a rule, add a literal, delete a literal, and induce a rule from a plan. Induction takes the last action the list failed to name. The subsequence runs from that action to the next goal atom that becomes true and stays true. Triangle tables (Fikes et al., 1972) regress the preimage. The new rule’s action is the missed action. Its goal condition is that goal atom. Its state condition starts smaller than the full preimage and grows until the rule reproduces the missed action. The rule is inserted before any existing rule that would have fired in the missed state.

At test time the planner is not called. The list runs until the goal holds, no rule applies, or a horizon is reached. Training problems are small. Test problems have more objects. That size jump is PG3’s definition of generalization.

### A blocksworld picture of their training

PG3 did not run this domain. The same operations, applied to blocks, look like this. `a`, `b`, and `c` start on the table. The goal is `(on a b)` and `(on b c)`. Suppose the list so far can only stack:

```text
holding(?x), clear(?y), (on ?x ?y) in the goal  ->  stack(?x, ?y)
```

A* pays cost 1 for `pickup(b)`, then takes `stack(b, c)` at cost 0, and likewise for `a`. The disagreement count is 2, the two pickups. Induction on the last miss builds a pickup rule whose action is `pickup` and whose goal condition is the atom that pickup was serving. Once those pickups also follow the list, they cost 0 too.

A compact stack-from-the-base policy can disagree with a particular A* trace that picks blocks up in a clumsy order. Plan comparison would reject the compact policy. Policy-guided A* can follow it and fill only the gaps, which is why PG3 prefers it. That preference is exactly what disappears if learning is forbidden to call the planner again.

### What we take from PG3

The rule form is the part that fits a PDDL System 1. State literals, goal literals, one lifted action. Goal atoms are already the final goal of the problem. A rule may mention a subset of them. Nobody has to supply a subgoal list.

The execution split also fits. Follow the list where it applies. Pay for search only at a gap. In PG3 that split is a training score. In our setting it is the runtime division of labor.

### What we do not take

The outer search over candidate lists, the inner A* that rolls a candidate into towers that were not built, and the demand that the finished list replace the planner. Those are how PG3 forces a complete solver. They are comparative evaluation of many hypotheses. Recognition-primed decision generates one action (Klein, 1989).

We also do not take first-match under a fixed object order, induction from a single trace straight into unsupervised firing, or a success metric that deletes the planner. The theorems do not license those steps for decision lists in any case (Yang et al., 2022).

## Learning from executed traces only

The constraint we adopted is stronger than “do not run PG3’s outer search.” Both the rule and the planner act in the simulator. The record of that execution is the only experience. The domain model may be used to read the record: which preconditions held, which goal atom an effect added. The update may not apply a candidate action in a state the agent did not visit, and it may not call A* to see how a gap could have been filled.

Under that constraint, PG3’s induce step still applies. Walk the recorded states. At the first planner step the current rules did not name, build one rule whose action is that step, whose goal condition is the goal atom the step served, and whose state literals are the observed preconditions, then lifted. Test the new rule by matching it against recorded states, including older traces. If the recorded action is not the unique grounding, specialize using a literal that is already in those records, or refuse the rule.

Checking recorded states is not a new execution. If the rule names the recorded action at every recorded state, the list imitates those traces. Agreement does not say what the rule will do on a state that has never been visited. That is discovered on a later execution.

Three losses remain even if the same planner is run forever.

The stored plan can be a bad teacher. If every trace picks up `a` before the base is ready and then recovers, every repair copies that detour. A shorter rule that always places the base first disagrees with the traces, so the recorded-state test rejects it. More runs of the same planner repeat the plan. PG3’s zero-cost rollout was built for this case (Yang et al., 2022). Giving it up means we do not inherit PG3’s policy, only a lifted imitation of the traces we happened to execute.

A local repair cannot rewrite the list. PG3 tries adding a condition, deleting a condition, deleting a rule, and moving a rule, then rescores. A first new rule that matches every recorded state can sit in front of a better rule forever. Extra traces keep failing unless a contradicted rule is edited in place. Nothing in a pure fit-to-traces test keeps the list short. The other stable outcome is one specific rule per trace. Those rules cover the traces and do not fire on a similar tower. Minton (1990) measured the related failure for macros: extra operators added to a search make the search worse. Our handoff avoids that only if a non-match calls the planner instead of becoming another operator inside the search.

The new rule acts in the world before any execution of it exists. Agreement with past states does not constrain the next tower. The expectancy check is what stops a wrong fire from continuing. Without it, the first wrong grounding is carried out, and “the goal is not true yet” never interrupts.

Two further errors shrink when a later task actually contradicts the rule. A goal condition tied to the wrong atom, and a tie between two blocks, can both be consistent with the old traces. A new tower can expose them. The same-planner bias, the inability to delete an earlier rule, and acting on an untested rule do not shrink just by collecting more traces of the same kind.

A mixed trace needs a cut. Steps the current rules already took are confirmations, not new labels. Only the planner’s steps may create or rewrite a rule. Otherwise System 1 retrains on its own actions, including a wrong action that the planner later repaired.

## Related systems

These are the planning systems that store something like a fast response. They are listed by what they store, and by whether a miss returns to search.

**Soar chunking** (Laird et al., 1986). When the agent cannot choose an operator, it searches in a subgoal. Chunking compiles that search into a production whose conditions are the features that mattered. The next time those features are present, the production fires and the impasse does not occur. This is the clearest statement of deliberation becoming recognition. The chunk is installed after one impasse, which is earlier than Kahneman and Klein’s practice requirement.

**ICARUS** (Langley and Choi, 2006). A skill has a start condition and an ordered body. Execution walks from the goal down the skill hierarchy and runs the skill whose start condition holds. Means-ends search runs when no skill path applies, and a solved trace is stored as a new skill. Later skills can call earlier ones. This is the closest architecture to a miniskill that fires on a match and leaves the unrecognized goal to search. The skill hierarchy is given a goal stack during search. At execution the stack is not a list of subgoals supplied by the task.

**Derivational analogy** (Carbonell, 1986; Veloso, 1994). A case stores the decisions of a past search, each justified by the goal literal it served. Replay reuses a decision whose justification still holds in the new initial state and the new final goal. Search restarts at the first failed justification. The match is against the final goal, which is the right grain if the task has no subgoal list. The stored object is a derivation, not a single action.

**PRIAR** (Kambhampati and Hendler, 1992). A plan is annotated with which step achieves which conjunct of the final goal. Reuse checks that annotation against the new problem. Again the input is one goal. The reused object is a whole annotated plan.

**Generalized plans with loops** (Srivastava et al., 2008; Winner and Veloso, 2003). A concrete plan is abstracted until repeated structure becomes a loop, together with an applicability condition. This is the `for i in range(n)` form a fixed-arity PDDL operator cannot express. PG3 gets variable height by firing one lifted rule again, not by storing a loop. Our checkpoint does the same for `stack`. An explicit loop is a later representation, not a requirement of the first slice.

**HTN-MAKER** (Hogg et al., 2008) and **Macro-FF** (Botea et al., 2005). Both learn reusable structure from traces or solutions, then put it back inside a planner. HTN-MAKER learns methods from annotated tasks. Macro-FF adds lifted macros to the domain and lets FF search. The fast part is a shorter search. Kahneman’s System 1 is the step on which search is not run. Minton (1990) is the warning that the macro version can lose even that speedup.

**Dual-process agents that are not PDDL rule learners.** SwiftSage (Lin et al., 2023) clones a next-action policy from expert traces and calls a language model when the action is invalid. Talker-Reasoner (Christakopoulou et al., 2024) separates a fast conversational response from a slower planner. Expert iteration (Anthony et al., 2017) trains a neural policy on the moves chosen by tree search. In each case the fast component proposes the next action from a learned function. None of them stores a lifted PDDL rule whose effect is checked, and none of them states Kahneman and Klein’s practice and validity conditions as the criterion for firing.

## Kahneman’s vocabulary in PDDL

Kahneman did not work on planning. Klein’s model was not encoded in PDDL.

Plan-SOFAI is the system that puts the vocabulary into classical planning (Fabiano et al., 2023). It is an instance of SOFAI (Booch et al., 2021; Ganapini et al., 2021). System 2 for classical problems is Fast Downward (Helmert, 2006). The released code runs PDDL domains, including blocksworld. System 1 is one of two memories. The case-based memory stores whole past plans and returns the plan whose problem is closest in edit distance or in overlap of the initial state and the goal. Plansformer emits a whole plan from a language model fine-tuned on instances and plans (Pallagani et al., 2022). A metacognitive check accepts the fast plan only after enough solutions have been stored. The paper’s default thresholds are 20 stored solutions before System 1 is eligible, and a confidence comparison before it is accepted. Otherwise Fast Downward solves the instance and the new plan is stored.

That is Kahneman’s split at the level of entire problems: a familiar problem is answered from memory, an unfamiliar one is searched, and a count of past experience gates the fast answer. It does not cut a trace into a cue–action rule, it does not fire in the middle of a tower, and it does not revise a rule when an effect fails. Two towers with different block names can look far apart as strings even when the same `stack` situation is present.

PG3 is the opposite crossing. It is PDDL, and it learns lifted rules, and it does not use Kahneman’s conditions. The checkpoint below is the combination neither system has run: a practiced cue–action rule inside a known PDDL domain, with the planner kept for every step the rule does not uniquely recognize.

## First checkpoint

The slice is small enough to implement, and it stays inside the constraints above.

Towers start with every block on the table. The domain is the ordinary blocksworld operators and is given. System 2 is a planner. System 1 may learn only `stack`. `pickup` and `putdown` stay with the planner, so the system never chooses which clear block to pick up. That choice is where a goal atom and the immediate action come apart, and it is where an arbitrary grounding would pretend to be a recognition.

A `stack` rule fires only when exactly one grounding matches. The expected add-effects are compared with the state the simulator returns. No unique match, a failed effect, or a repeated state calls the planner. Only the planner’s steps in that trace may create or rewrite a rule. A System 1 step that produced the expected effect increments the confirmation count and writes nothing new.

Training towers are executed one by one, with updates on. Test towers are then run with the rule set frozen. Frozen evaluation is the first measurement. Continual update during the test phase waits.

Defaults for the quantities the literature leaves open:

- A rule stored from one trace may not fire on its own. It becomes System 1 after the same cue has been followed by the expected effect twice.
- The cue is the preconditions of `stack` that held in the observed state, lifted, plus the goal atom that action added, `(on ?x ?y)`. A literal that was not in that state or in the goal is not added.
- If a fire’s effect is wrong, and exactly one literal is true of the successful uses and false in the failed state, that literal is added to the rule. Otherwise the rule is retired. A second `stack` rule is not appended behind the one that fired.

Record, on the test towers, the number of steps a practiced rule took with the right effect, the number of fires whose effect was wrong, and the number of steps passed to the planner. Task success is recorded and is not the headline.

Left out of this run: updating during the test phase, towers that must be taken apart, an explicit loop over height, a language model for cues the literals cannot express, and domain learning. The worry that a distant goal atom is a bad cue for an immediate action is also outside the run, because the only learned action is the one that adds a goal atom directly.

## References

Anthony, T., Tian, Z., & Barber, D. (2017). Thinking fast and slow with deep learning and tree search. *Advances in Neural Information Processing Systems, 30*.

Bonet, B., & Geffner, H. (2001). Planning as heuristic search. *Artificial Intelligence, 129*(1–2), 5–33.

Booch, G., Fabiano, F., Horesh, L., Kate, K., Lenchner, J., Linck, N., Loreggia, A., Murugesan, K., Mattei, N., Rossi, F., & Srivastava, B. (2021). Thinking fast and slow in AI. *Proceedings of the AAAI Conference on Artificial Intelligence, 35*(17), 15042–15046.

Botea, A., Enzenberger, M., Müller, M., & Schaeffer, J. (2005). Macro-FF: Improving AI planning with automatically learned macro-operators. *Journal of Artificial Intelligence Research, 24*, 581–621.

Carbonell, J. G. (1986). Derivational analogy: A theory of reconstructive problem solving and expertise acquisition. In R. S. Michalski, J. G. Carbonell, & T. M. Mitchell (Eds.), *Machine learning: An artificial intelligence approach* (Vol. 2). Morgan Kaufmann.

Christakopoulou, K., Mourad, S., & Matarić, M. (2024). Agents thinking fast and slow: A talker-reasoner architecture. arXiv:2410.08328.

Ericsson, K. A. (2006). The influence of experience and deliberate practice on the development of superior expert performance. In K. A. Ericsson, N. Charness, P. J. Feltovich, & R. R. Hoffman (Eds.), *The Cambridge handbook of expertise and expert performance* (pp. 683–703). Cambridge University Press.

Fabiano, F., Pallagani, V., Ganapini, M. B., Horesh, L., Loreggia, A., Murugesan, K., Rossi, F., & Srivastava, B. (2023). Fast and slow planning. arXiv:2303.04283.

Fikes, R. E., Hart, P. E., & Nilsson, N. J. (1972). Learning and executing generalized robot plans. *Artificial Intelligence, 3*(4), 251–288.

Ganapini, M. B., Campbell, M., Fabiano, F., Horesh, L., Lenchner, J., Loreggia, A., Mattei, N., Rossi, F., Srivastava, B., & Venable, K. B. (2021). Thinking fast and slow in AI: The role of metacognition. arXiv:2110.01834.

Helmert, M. (2006). The Fast Downward planning system. *Journal of Artificial Intelligence Research, 26*, 191–246.

Hogarth, R. M. (2001). *Educating intuition*. University of Chicago Press.

Hogg, C., Muñoz-Avila, H., & Kuter, U. (2008). HTN-MAKER: Learning HTNs with minimal additional knowledge engineering required. In *Proceedings of the AAAI Conference on Artificial Intelligence*.

Kahneman, D. (2011). *Thinking, fast and slow*. Farrar, Straus and Giroux.

Kahneman, D., & Frederick, S. (2002). Representativeness revisited: Attribute substitution in intuitive judgment. In T. Gilovich, D. Griffin, & D. Kahneman (Eds.), *Heuristics and biases: The psychology of intuitive judgment* (pp. 49–81). Cambridge University Press.

Kahneman, D., & Klein, G. (2009). Conditions for intuitive expertise: A failure to disagree. *American Psychologist, 64*(6), 515–526.

Kahneman, D., & Tversky, A. (1982). The simulation heuristic. In D. Kahneman, P. Slovic, & A. Tversky (Eds.), *Judgment under uncertainty: Heuristics and biases* (pp. 201–208). Cambridge University Press.

Kambhampati, S., & Hendler, J. A. (1992). A validation-structure-based theory of plan modification and reuse. *Artificial Intelligence, 55*(2–3), 193–258.

Khardon, R. (1999). Learning action strategies for planning domains. *Artificial Intelligence, 113*(1–2), 125–148.

Kienle, C., Alt, B., Arenz, O., & Peters, J. (2025). Learning hierarchical domain models through environment-grounded interaction. arXiv:2505.13497.

Klein, G. A. (1989). Recognition-primed decisions. In W. B. Rouse (Ed.), *Advances in man-machine systems research* (Vol. 5, pp. 47–92). JAI Press.

Klein, G. A., Calderwood, R., & Clinton-Cirocco, A. (1986). Rapid decision making on the fire ground. *Proceedings of the Human Factors Society Annual Meeting, 30*(6), 576–580.

Laird, J. E., Rosenbloom, P. S., & Newell, A. (1986). Chunking in Soar: The anatomy of a general learning mechanism. *Machine Learning, 1*(1), 11–46.

Langley, P., & Choi, D. (2006). A unified cognitive architecture for physical agents. In *Proceedings of the AAAI Conference on Artificial Intelligence*.

Levine, J., & Humphreys, D. (2003). Learning action strategies for planning domains using genetic programming. In *Applications of evolutionary computing* (pp. 684–695). Springer.

Lin, B. Y., Fu, Y., Yang, K., Brahman, F., Huang, S., Bhagavatula, C., Ammanabrolu, P., Choi, Y., & Ren, X. (2023). SwiftSage: A generative agent with fast and slow thinking for complex interactive tasks. *Advances in Neural Information Processing Systems, 36*. arXiv:2305.17390.

Minton, S. (1990). Quantitative results concerning the utility of explanation-based learning. *Artificial Intelligence, 42*(2–3), 363–391.

Mooney, R. J., & Califf, M. E. (1995). Induction of first-order decision lists: Results on learning the past tense of English verbs. *Journal of Artificial Intelligence Research, 3*, 1–24.

Pallagani, V., Muppasani, B., Murugesan, K., Rossi, F., Horesh, L., Srivastava, B., Fabiano, F., & Loreggia, A. (2022). Plansformer: Generating symbolic plans using transformers. arXiv:2212.08681.

Simon, H. A. (1955). A behavioral model of rational choice. *The Quarterly Journal of Economics, 69*(1), 99–118.

Simon, H. A. (1992). What is an “explanation” of behavior? *Psychological Science, 3*(3), 150–161.

Srivastava, S., Immerman, N., & Zilberstein, S. (2008). Learning generalized plans using abstract counting. In *Proceedings of the AAAI Conference on Artificial Intelligence*.

Stanovich, K. E., & West, R. F. (2000). Individual differences in reasoning: Implications for the rationality debate? *Behavioral and Brain Sciences, 23*(5), 645–665.

Veloso, M. M. (1994). Flexible strategy learning: Analogical replay of problem solving episodes. In *Proceedings of the AAAI Conference on Artificial Intelligence*.

Winner, E., & Veloso, M. (2003). DISTILL: Learning domain-specific planners by example. In *Proceedings of the Twentieth International Conference on Machine Learning*.

Yang, R., Silver, T., Curtis, A., Lozano-Pérez, T., & Kaelbling, L. P. (2022). PG3: Policy-guided planning for generalized policy generation. In *Proceedings of the Thirty-First International Joint Conference on Artificial Intelligence*. arXiv:2204.10420.
