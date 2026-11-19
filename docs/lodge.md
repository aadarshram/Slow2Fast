# LODGE

LODGE learns a hierarchical PDDL domain while it plans. An LLM proposes operators, a goal, and, in some settings, predicates. A simulator then executes the low-level skills those operators map to, and mismatches between the predicted symbolic state and the observed symbolic state are fed back so the LLM can edit the domain.

The code does not start from a blank world. It is given a skill library, object types, a scene, and usually a way to read predicates off that scene. What it has to invent is the action model: operator names, parameters, preconditions, effects, which skill each operator calls, and how composite operators break into subdomains. The goal formula is also invented from a natural-language instruction. A ground-truth PDDL problem file is not an input.

The paper is Kienle, Alt, Arenz, and Peters, “Learning Hierarchical Domain Models through Environment-Grounded Interaction” (arXiv:2505.13497v3). The implementation lives in the handoff archive `ref_codes/dea-research-handoff-final-2026-10-06.tar.gz`. The pieces used below are extracted beside that archive.

## Where the code is

`ref_codes/task-planner-lodge` is the planner. The loop starts at `NLActionNode` and is driven by `CompositeActionNode`.

`ref_codes/state-estimation` writes and checks the Python functions that evaluate invented predicates.

`ref_codes/lodge-ipc` is the household and logistics runner. `ref_codes/lodge-furniturebench` is the robotic assembly runner. The hundreds of `p01.pddl` files in the archive are evaluation scenes. The runners do not load them as the thing to learn.

## What a run is trying to produce

One run takes one instruction and one scene. It returns three things: a hierarchical domain, a problem (objects, init, goal), and a plan that the simulator actually executed.

The domain is a tree. The root level holds abstract operators. An operator that the LLM maps to several skills becomes a parent, and a child domain is learned underneath it. Each operator stores the Python skill calls that implement it once those calls have been checked in the simulator (`mapped_skill_sequence`).

Predicates carry a parent operator, a description, and a kind. `state` predicates are things that can change and that a classifier could read from the scene. `other` predicates are static facts, such as affordances. A predicate is `predefined` when the environment already knows how to evaluate it.

## Inputs the system is given

These are fixed before the LLM writes any operator.

**Instruction.** A short natural-language task, for example “put apple_2 on side_table_2” or “assemble the lamp”. This is the only statement of the goal.

**Skill library.** Python stubs with docstrings and no bodies. Household has skills such as `pick_up_an_object_on_or_in_a_furniture_piece_or_an_appliance`. The lamp has skills such as `hover_above_part` and `screw_touching_parts_together`. The LLM may only call these functions. It does not invent new motor skills. An optional flag strips the docstrings. Another flag appends extra unused skills.

**Object types and the object list.** Household types are `agent`, `household_object`, and `furniture_appliance`. The lamp uses `robot`, `part`, and `table`. The object names come from the scene, not from the LLM.

**A simulator that can run those skills.** Household and logistics are symbolic simulators. FurnitureBench is a remote physics simulator behind an HTTP API. The simulator returns either a new state or an error string. With `--hide-env-feedback`, a failed household skill is reported only as “cannot be executed”, without the simulator’s own message.

**Domain knowledge text.** A free-text note inserted into the prompts. The household file shipped with the runner is empty. The lamp file describes the Franka arm, the table, and what “aligned” means for parts. The IPC runner can turn this note off.

**Retry budgets.** Default IPC limits are 20 domain-edit retries and 10 environment retries. FurnitureBench uses 40 and 20. Hitting either limit stops the run.

**Classical planning tools.** Fast Downward (`lama-first`, 30 second limit) and VAL. They search and check the current candidate domain. They are not given the ground-truth domain.

## What it identifies on its own

**Operators.** Names, parameters, preconditions, effects, and a one-line description. The prompt asks for general operators, not object-specific ones, and prefers a few high-level operators over one operator per skill.

**The goal.** A PDDL formula written from the instruction. Temporal wording in the instruction is ignored.

**Skill grounding.** For each ground action in the plan, the LLM returns a list of calls into the skill library. One call means the operator is primitive and can be executed. Several calls mean it is composite and must be decomposed. An empty list is treated as a domain error: change the operator or drop it.

**Child domains.** A composite operator is broken into lower-level operators that cover the suggested skill sequence. New predicates may be added at that level. After the child plan executes, its observed effect is checked against the parent operator’s effect.

**Edits after failure.** If execution, a precondition check, or the final goal check disagrees with the model, an LLM error reasoner decides whether the operator definitions are wrong. The parent domain is then regenerated and the planner tries again. The chat is capped so only the latest domain, not the whole history, stays in context.

**Predicates, only in the learning settings.** If the domain skeleton has no predicates, the prompt switches to “learn predicates”: the LLM invents predicate names, arguments, a `state` or `other` tag, and a description a classifier could test. In the default IPC setting the predicate list is already filled in, and the LLM is told to use it.

**Init atoms the environment cannot see.** The LLM may add or remove atoms whose predicates are not supported by the simulator. Atoms of supported predicates are dropped when the LLM’s text is parsed, and the simulator writes those atoms itself.

## Oracle information, by setting

“Oracle” here means a fact or a classifier supplied by the experiment, not produced by the learning loop.

### IPC household and logistics, default

This is `lodge-ipc/scripts/01-run_lodge.py` without `--learn-predicates`.

The domain skeleton (`domain_skeleton.json`) already lists types and a fixed predicate vocabulary. Every predicate is marked `predefined`. There are no operators in the skeleton.

`HouseholdMotionValidator.validate_predicate` is a hand-written classifier. It reads the simulator’s symbolic state and implements predicates such as `at-agent`, `holding`, `sliced`, `heated`, `openable`, and `stacked-on`. The same list is returned by `get_supported_predicates`. A predicate the validator does not know raises an error and is skipped.

The scene itself is also given. `PlanningBenchmarkSampleGenerator` reads `household_planning_tasks.json` from the Guan et al. benchmark (24 household instructions). Each task has object names, types, and a symbolic state such as “drawer_1 is opened”. That state is loaded into the simulator before planning starts. The LLM never sees this JSON. It sees the predicate atoms the validator computes from it.

`domain.pddl` in the data folder is the ground-truth domain. The runner loads it only for the `--show-op-signature` ablation, and even then it copies operator names and parameters with empty preconditions and empty effects. `predicate_descriptor.py` is not read by this runner.

### IPC with `--learn-predicates`

Household only. The skeleton’s predicates are deleted. Types stay, restricted to `household_object`, `furniture_appliance`, `small_receptacle`, `small_items`, and `agent`.

The LLM invents the predicates. Evaluation is no longer the hand-written `if pred_name == ...` table. `PredicateGrounder` asks the LLM to fill in a Python function whose arguments are typed objects. The body may read the fields in `household_predicates_object_api.py`: locations, `clean`, `sliced`, `door_open`, `pickupable`, and so on.

That object API is still an oracle. The classifier is generated from the predicate description plus this structured state. It is not fit to labels collected during the run. There is no image and no reply buffer on this path.

### FurnitureBench

`run_lodge.py` has four methods.

`fixed` loads a domain skeleton and a problem skeleton from disk and uses a remote validator that already knows its predicates.

`none` keeps a single predefined predicate, `assembled(?obj1, ?obj2)`, and tells the LLM the initial layout in the instruction text.

`learn` and `learn-finetune` are the paper’s predicate-invention setting. `create_se_motion_validator` resets the simulator, reads the live object list, and builds an empty domain whose types are the types of those objects. The runner then inserts the same predefined `assembled` predicate. `learn-finetune` instead starts from a domain and from classifier code already saved for a related piece of furniture.

For invented `state` predicates the loop is:

1. After each skill, the numeric state and a camera image are stored in a reply buffer.
2. A VLM labels the new predicates on that image, using the previous image, the skill that just ran, and the previous labels.
3. An LLM writes a Python classifier over a typed view of the numeric state (poses and similar fields, or the custom `llm_code_interface.py` API).
4. The classifier is compared with the VLM labels. Thresholds inside the function can be searched, and if the agreement stays low the LLM is shown a few disagreements and asked to rewrite the function.

The VLM labels are pseudo-labels, not the simulator’s ground-truth atoms. The simulator’s own `get_predicates_evaluation` is still unioned in, so predicates the backend already knows (including predefined ones) stay oracle.

## Problem files

LODGE does not take a finished PDDL problem as the learning problem.

On IPC, `PlanningBenchmarkSampleGenerator.generate` returns three things: the instruction string, the simulator state, and a `LODGEPDDLProblem` that contains only objects. Init is `None`. Goal is `None`.

Init is then overwritten by `inject_init_predicates`. The validator grounds every supported predicate on every well-typed argument tuple and writes true and false atoms. Predicates it cannot evaluate are left as whatever the problem already had.

The goal is whatever the LLM writes under “Change Goal State” while it writes the domain. Later, if the executed plan does not achieve that goal, the unmet-goal prompt asks the LLM to repair the domain or the goal.

The FurnitureBench problem skeleton is the same shape. `problem-skeleton.json` for the lamp lists `arm`, `lamp_bulb`, `lamp_hood`, and `lamp_base`, with `initial_state` and `goal_state` both null. In the `learn` method the skeleton is not even read from that file. Objects are taken from the live simulator.

The files `problems/p01.pddl`, `p02.pddl`, and the matching `*-sample_plan.plan` files are held-out checks. A lamp problem file, for example, already contains `(hovered_above lamp_base)`, `(screwable ...)`, and the goal `(assembled lamp_bulb lamp_base)`. None of that is passed into `NLActionNode`.

Across several IPC tasks, `--learn-one-domain` keeps operators that have already been verified in the simulator and copies non-predefined `other` atoms from the previous problem’s init into the next skeleton. `state` atoms are not copied, because they belong to the new scene. The new scene’s supported predicates are still filled by the validator.

## First contact with the environment

The environment is touched before any operator exists.

1. The runner loads the scene into the simulator. IPC copies the benchmark state and calls `init_state`. FurnitureBench calls `reset(seed=1)` on the remote backend and stores the environment hash.
2. If the skeleton already has predicates, `NLActionNode` immediately calls `inject_init_predicates`. The LLM’s first prompt therefore contains a grounded init, not an empty one.
3. The first LLM call is still textual. It sees the instruction, the skill signatures, the types, the objects, the domain-knowledge note, and either the predefined predicates or a request to invent them. It does not see an image on the IPC path.
4. Only after a plan exists does a skill run. `PDDLPredefinedActionNode` turns the PDDL arguments into a Python call and `MotionValidator.validate` does four things: restore the simulator to the hash from before this action, read the predicate state, run the skill, read the predicate state again, and compare the change with the effect the operator predicted.

A skill that throws is a failure even before that comparison. A `TypeError` is treated as a bad translation from PDDL arguments to Python. A `ValueError` is treated as an illegal action in the current state.

## How the domain is learned

`NLActionNode.plan` is the root. It always regenerates the root domain from the instruction. A shortcut that would only regenerate the problem, leaving a cached domain, is present and forced off (`if False`).

**Propose.** `generate_definitions_from_text` fills `pddl-problem-domain-gen-prompt.xml`, or the learn-predicates variant when the skeleton has zero predicates. The model must answer in a fixed outline: explanation, action additions or edits, predicate additions, init edits, and a full goal replacement. The parser in `pddl_parse_utils.py` applies those edits onto the skeleton. Syntax or VAL errors are pasted back to the model, and each such round spends one validation retry.

**Plan.** `retry_ai_planning` asks Fast Downward for a plan in the current domain and problem. VAL then checks that plan. If `--use-ai-planner` is set and both succeed, that plan is kept. Otherwise the LLM is asked to write a plan. When Fast Downward did find a plan, that plan can be shown to the LLM as a hint (`use_ai_plan_for_llm_planning`, on by default in the IPC runner, off for FurnitureBench). The hint is a plan in the candidate domain, not a demonstration from the ground-truth domain. If the LLM’s plan does not parse or VAL rejects it, the domain is regenerated with the error attached.

**Check the init.** Before any skill runs, the grounded init is compared with a fresh read of the simulator. A mismatch is sent back as “expected versus observed”, and the root domain is regenerated.

**Walk the plan.** For each ground action, preconditions are checked with VAL against the symbolic state reached so far. A failure asks the LLM which earlier operator to blame. Then the action is grounded to skills.

A single skill is executed as above. If the observed predicate change disagrees with the operator’s effect, a second LLM call classifies the failure. The classes that bubble up as “edit the PDDL” are `pddl-fix`, a bad choice of earlier skills, or a bad instantiation. The parent node then edits the operators and replans. If the skill choice itself was wrong, the same node is asked to pick a different skill sequence. Repeating the identical sequence escalates to a domain edit.

Several skills open a child node. The child LLM writes a subdomain whose operators cover that skill list, plans inside the child, and executes. The parent’s effect is then compared with what the simulator shows, but only on predicates that belong to the parent level. A mismatch is called goal overshoot: the child did something the parent operator did not declare, and the parent domain must be repaired. Child domains do not catch every domain error, only errors that name one of their own operators. The root catches all of them.

**Stop.** When the whole plan has been executed, the goal atoms that the simulator can evaluate must hold. If they do not, the unmet-goal prompt is appended and the level replans. On success, the root returns the plan result, the full domain tree, and the symbolic goal state obtained by rolling the operators forward.

Partial replanning is file-based. Each action has a directory. If a later retry changes only the effects of an operator, cached child work is kept. If the parameters or the preconditions change, that action and the ones after it are redone.

## What gets saved

The run directory is the memory of the learned model. The important files are:

`generated-domain.json` at the root of the run. This is the full tree: every operator, its parent id, its description, whether it has been verified, and the skill sequence mapped to it. Predicates are stored with their description, `state` or `other`, `predefined`, and parent operator. The IPC runner also copies the finished tree to `domain.json`.

`generated-problem.json` at each level. Objects, init atoms, and the goal formula for that level. Child levels have their own problem, whose goal is the effect of the parent action being decomposed.

`init-domain.json` at each level, so a retry can show the model only what changed.

`ai-plan.cache.plan` and `llm-plan.cache.plan`.

`sub-actions/<index>-<operator>/` for the walk. A primitive leaf stores `skills-code.py`, `decide-whether-primitive.json`, and `env-state.hash`. A composite leaf stores another `generated-domain.json` pattern one level down, plus chats.

Chat dumps (`*.chat`, `generated-chat.json`) and `planner.log`.

`storage.json` with the remaining retry counts. `textgen-api-usage.json` with token use. A `failed` file if the run died. `backups/b-<n>/` is a full copy of the run directory taken before each validation retry.

Predicate classifiers, when they are learned, are Python files under `grounding_code/`. FurnitureBench also stores `reply_buffer/` (states, images, VLM labels) and `vlm_grounder/`.

Nothing here is a PDDL file ready to drop into a planner until it is rendered. `LODGEPDDLDomain.to_string()` is what Fast Downward and VAL receive, written to a temporary directory and discarded. The durable form is the JSON tree.

## What this means if we reuse it

A LODGE-style learner in CMC should expect the same split.

Give it the skill stubs, the types, the object names, and a simulator that can run a skill and report success or failure. Decide explicitly whether predicate symbols and their classifiers are given, as in default IPC, or invented, as in FurnitureBench `learn`.

Do not give it the ground-truth domain, and do not give it a finished problem file. Give it the instruction and let it write the goal. Let the environment write the init atoms it knows how to test.

The learned artifact to keep is the hierarchical JSON domain plus the per-level problem, not only a flat `domain.pddl`. The skill mapping on each verified operator is part of the model. Without it the operator cannot be executed again.
