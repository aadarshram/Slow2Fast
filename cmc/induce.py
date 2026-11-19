"""Induce lifted cue-action rules from System 2 traces and the domain model only.

After each System 2 lesson: induce (or confirm), then PG3 add condition.
Delete condition is implemented but disabled.
"""

from cmc.blocksworld import apply
from cmc.domain import OPERATORS, add_effects, lifted_preconditions


class InducedRule:
    def __init__(self, action_name, param_vars, state_pos, goal_pos, goal_neg):
        self.action_name = action_name
        self.param_vars = tuple(param_vars)
        self.state_pos = list(state_pos)
        self.goal_pos = list(goal_pos)
        self.goal_neg = list(goal_neg)
        self.confirmations = 0

    def signature(self):
        return (
            self.action_name,
            self.param_vars,
            tuple(self.state_pos),
            tuple(self.goal_pos),
            tuple(self.goal_neg),
        )


class InducedLibrary:
    def __init__(self, threshold=2):
        self.threshold = threshold
        self.rules = []
        self.traces = []

    def counts(self):
        return {f"r{i}": rule.confirmations for i, rule in enumerate(self.rules)}

    def propose(self, state, goal):
        found = []
        for index, rule in enumerate(self.rules):
            if rule.confirmations < self.threshold:
                continue
            for action in groundings(rule, state, goal):
                found.append((f"r{index}", action))
        if len(found) == 1:
            return found[0]
        return None

    def diagnose(self, state, goal):
        practiced = []
        unpracticed = []
        for index, rule in enumerate(self.rules):
            hits = [(f"r{index}", action) for action in groundings(rule, state, goal)]
            if rule.confirmations >= self.threshold:
                practiced.extend(hits)
            else:
                unpracticed.extend(hits)
        if len(practiced) == 1:
            return "unique", practiced
        if len(practiced) > 1:
            return "multi_match", practiced
        if unpracticed:
            return "below_threshold", unpracticed
        return "no_match", []

    def observe(self, state, goal, action, plan=None):
        state = frozenset(state)
        goal = frozenset(goal)
        self._repair_fat_goals(state, goal, action)

        agreeing = [rule for rule in self.rules if groundings(rule, state, goal) == [action]]
        if len(agreeing) == 1:
            agreeing[0].confirmations += 1
            self.traces.append((state, goal, action))
        elif len(agreeing) > 1:
            self.traces.append((state, goal, action))
        else:
            plan = list(plan) if plan else [action]
            rule = induce_from_plan(state, goal, plan)
            if rule is None:
                self.traces.append((state, goal, action))
            else:
                matched_existing = False
                for existing in self.rules:
                    if existing.signature() == rule.signature():
                        if groundings(existing, state, goal) == [action]:
                            existing.confirmations += 1
                        self.traces.append((state, goal, action))
                        matched_existing = True
                        break
                if not matched_existing:
                    if not _consistent(rule, self.traces) or _conflicts_with_library(
                        rule, self.rules, self.traces
                    ):
                        rule = _grow_state(rule, state, goal, action, self.rules, self.traces)
                    if (
                        rule is not None
                        and _consistent(rule, self.traces)
                        and not _conflicts_with_library(rule, self.rules, self.traces)
                        and groundings(rule, state, goal) == [action]
                    ):
                        rule.confirmations = 1
                        self.rules.append(rule)
                    self.traces.append((state, goal, action))

        self._add_conditions(state, goal, action)
        # Delete condition disabled: keep only add condition.

    def note_success(self, name):
        self.rules[int(name[1:])].confirmations += 1

    def _add_conditions(self, state, goal, action):
        """PG3 Add Condition."""
        for _ in range(32):
            hits = [(rule, groundings(rule, state, goal)) for rule in self.rules]
            hits = [(rule, got) for rule, got in hits if got]
            actions = [act for _rule, got in hits for act in got]
            if len(actions) <= 1 and (not actions or actions[0] == action):
                return
            progressed = False
            for rule, got in hits:
                if got == [action]:
                    continue
                if _add_condition_to_rule(rule, state, goal, action, self.rules, self.traces):
                    progressed = True
                    break
            if progressed:
                continue
            winners = [rule for rule, got in hits if got == [action]]
            for rule in winners[1:]:
                if _add_condition_exclude(rule, state, goal, action, self.traces):
                    progressed = True
                    break
            if not progressed:
                return

    def _delete_conditions(self):
        """PG3 Delete Condition on state, goal_pos, and goal_neg (trace-safe only)."""
        changed = True
        while changed:
            changed = False
            for rule in self.rules:
                required = set(lifted_preconditions(rule.action_name, rule.param_vars))
                for index, lit in enumerate(list(rule.state_pos)):
                    if lit in required and rule.state_pos.count(lit) <= 1:
                        continue
                    new_state = list(rule.state_pos)
                    del new_state[index]
                    trial = InducedRule(
                        rule.action_name,
                        rule.param_vars,
                        new_state,
                        list(rule.goal_pos),
                        list(rule.goal_neg),
                    )
                    trial.confirmations = rule.confirmations
                    if _edit_ok(rule, trial, self.rules, self.traces):
                        rule.state_pos = trial.state_pos
                        changed = True
                        break
                if changed:
                    break
                for index, lit in enumerate(list(rule.goal_pos)):
                    new_goal = list(rule.goal_pos)
                    del new_goal[index]
                    trial = InducedRule(
                        rule.action_name,
                        rule.param_vars,
                        list(rule.state_pos),
                        new_goal,
                        list(rule.goal_neg),
                    )
                    trial.confirmations = rule.confirmations
                    if _edit_ok(rule, trial, self.rules, self.traces):
                        rule.goal_pos = trial.goal_pos
                        changed = True
                        break
                if changed:
                    break
                for index, lit in enumerate(list(rule.goal_neg)):
                    new_neg = list(rule.goal_neg)
                    del new_neg[index]
                    trial = InducedRule(
                        rule.action_name,
                        rule.param_vars,
                        list(rule.state_pos),
                        list(rule.goal_pos),
                        new_neg,
                    )
                    trial.confirmations = rule.confirmations
                    if _edit_ok(rule, trial, self.rules, self.traces):
                        rule.goal_neg = trial.goal_neg
                        changed = True
                        break
                if changed:
                    break

    def _repair_fat_goals(self, state, goal, action):
        for rule in self.rules:
            if rule.action_name != action[0]:
                continue
            if groundings(rule, state, goal) == [action]:
                continue
            if not _state_supports_action(rule, state, action):
                continue
            repaired = _relax_goal_pos(rule, state, goal, action, self.traces)
            if repaired is None:
                continue
            rule.goal_pos = repaired.goal_pos
            rule.goal_neg = repaired.goal_neg


def induce_from_plan(state, goal, plan):
    if not plan:
        return None
    action = plan[0]
    if action[0] not in OPERATORS:
        return None
    permanent = _permanent_goal_atom(state, goal, plan, action)
    gatom = permanent[1] if permanent is not None else None
    seed = set(action[1])
    seed |= {arg for _pred, args in goal for arg in args}
    if gatom is not None:
        seed |= set(gatom[1])
    objects = _related_objects(state, seed)
    mapping = _var_map(action, gatom, objects)
    param_vars = tuple(mapping[arg] for arg in action[1])
    goal_pos = _lift_complete_goal(goal, objects, mapping, gatom)
    goal_neg = []
    state_pos = list(lifted_preconditions(action[0], param_vars))
    rule = InducedRule(action[0], param_vars, state_pos, goal_pos, goal_neg)
    if groundings(rule, state, goal) != [action]:
        rule = _grow_state(rule, state, goal, action, [], [])
        if rule is None:
            return None
    return _minimize_state(rule, state, goal, action)


_GROUND_CACHE = {}


def groundings(rule, state, goal):
    """Same result as before; memoised because the same (rule, state, goal) is matched many times per step."""
    key = (
        rule.action_name,
        rule.param_vars,
        tuple(rule.state_pos),
        tuple(rule.goal_pos),
        tuple(rule.goal_neg),
        frozenset(state),
        frozenset(goal),
    )
    hit = _GROUND_CACHE.get(key)
    if hit is None:
        if len(_GROUND_CACHE) > 60_000:
            _GROUND_CACHE.clear()
        hit = _GROUND_CACHE[key] = tuple(_groundings_uncached(rule, state, goal))
    return list(hit)


def _groundings_uncached(rule, state, goal):
    state = set(state)
    goal = set(goal)
    found = []
    for binding in _bindings(sorted(_rule_vars(rule)), _blocks(state, goal)):
        if not _holds(rule, state, goal, binding):
            continue
        action = (rule.action_name, tuple(binding[var] for var in rule.param_vars))
        if action not in found:
            found.append(action)
    return found


def _lift_complete_goal(goal, objects, mapping, gatom):
    goal_pos = []
    if ("handempty", ()) in goal:
        goal_pos.append(("handempty", ()))
    if gatom is not None and (not gatom[1] or set(gatom[1]) <= objects):
        lifted = (gatom[0], tuple(mapping[arg] for arg in gatom[1]))
        if lifted not in goal_pos:
            goal_pos.append(lifted)
    for pred, args in sorted(goal):
        if not args:
            continue
        if set(args) <= objects:
            lifted = (pred, tuple(mapping[arg] for arg in args))
            if lifted not in goal_pos:
                goal_pos.append(lifted)
    return goal_pos


def _relax_goal_pos(rule, state, goal, action, traces):
    trial = InducedRule(
        rule.action_name, rule.param_vars, list(rule.state_pos), list(rule.goal_pos), list(rule.goal_neg)
    )

    def ok():
        return groundings(trial, state, goal) == [action] and _consistent(trial, traces)

    if ok():
        return trial
    while not ok():
        droppable = [
            lit for lit in trial.goal_pos if not _goal_lit_possible(trial, lit, state, goal, action)
        ]
        if droppable:
            droppable.sort(key=lambda lit: (-len(lit[1]), str(lit)))
            trial.goal_pos = [lit for lit in trial.goal_pos if lit != droppable[0]]
            continue
        if trial.goal_pos:
            options = []
            for lit in list(trial.goal_pos):
                candidate = InducedRule(
                    trial.action_name,
                    trial.param_vars,
                    trial.state_pos,
                    [item for item in trial.goal_pos if item != lit],
                    trial.goal_neg,
                )
                if groundings(candidate, state, goal) == [action] and _consistent(candidate, traces):
                    options.append(candidate)
            if options:
                options.sort(key=lambda item: -len(item.goal_pos))
                return options[0]
            trial.goal_pos = trial.goal_pos[:-1]
            continue
        if trial.goal_neg:
            trial.goal_neg = trial.goal_neg[:-1]
            continue
        return None
    return trial


def _goal_lit_possible(rule, lit, state, goal, action):
    state_vars = set(rule.param_vars)
    for item in rule.state_pos:
        state_vars.update(item[1])
    blocks = _blocks(state, goal)
    if len(state_vars) > len(blocks):
        return False
    for binding in _bindings(sorted(state_vars), blocks):
        if not _state_holds(rule, set(state), binding):
            continue
        if tuple(binding[var] for var in rule.param_vars) != action[1]:
            continue
        needed = [var for var in lit[1] if var not in binding]
        if not needed:
            if _ground(lit, binding) in set(goal):
                return True
            continue
        unused = [block for block in blocks if block not in binding.values()]
        if len(needed) > len(unused):
            continue
        for ext in _bindings(needed, unused):
            full = dict(binding)
            full.update(ext)
            if _ground(lit, full) in set(goal):
                return True
    return False


def _state_supports_action(rule, state, action):
    if rule.action_name != action[0]:
        return False
    state_vars = set(rule.param_vars)
    for lit in rule.state_pos:
        state_vars.update(lit[1])
    blocks = _blocks(state, set())
    if len(state_vars) > len(blocks):
        return False
    for binding in _bindings(sorted(state_vars), blocks):
        if tuple(binding[var] for var in rule.param_vars) != action[1]:
            continue
        if _state_holds(rule, set(state), binding):
            return True
    return False


def _state_holds(rule, state, binding):
    for literal in rule.state_pos:
        try:
            if _ground(literal, binding) not in state:
                return False
        except KeyError:
            return False
    return True


def _grow_state(rule, state, goal, action, rules, traces):
    objects = _related_objects(state, set(action[1]))
    for _pred, args in goal:
        objects |= set(args)
    objects = _related_objects(state, objects)
    permanent = _permanent_goal_atom(state, goal, [action], action)
    gatom = permanent[1] if permanent is not None else None
    mapping = _var_map(action, gatom, objects)
    pool = _lift_state_pool(state, objects, mapping)
    neg_pool = sorted(
        {
            (pred, tuple(mapping[arg] for arg in args))
            for pred, args in state
            if args and set(args) <= objects and (pred, args) not in set(goal)
        }
    )
    candidate = InducedRule(
        rule.action_name,
        tuple(mapping[arg] for arg in action[1]) if rule.param_vars else rule.param_vars,
        list(rule.state_pos),
        list(rule.goal_pos),
        list(rule.goal_neg),
    )
    if len(candidate.param_vars) != len(action[1]):
        candidate.param_vars = tuple(mapping[arg] for arg in action[1])
    remaining = [lit for lit in pool if lit not in candidate.state_pos]
    neg_remaining = [lit for lit in neg_pool if lit not in candidate.goal_neg]

    def ok(item):
        return (
            groundings(item, state, goal) == [action]
            and _consistent(item, traces)
            and not _conflicts_with_library(item, rules, traces)
        )

    while not ok(candidate):
        best = None
        best_score = None
        for lit in remaining:
            trial = InducedRule(
                candidate.action_name,
                candidate.param_vars,
                candidate.state_pos + [lit],
                candidate.goal_pos,
                candidate.goal_neg,
            )
            got = groundings(trial, state, goal)
            score = (len(got), 0 if got == [action] else 1)
            if got and (best_score is None or score < best_score):
                best = ("state", lit)
                best_score = score
        for lit in neg_remaining:
            trial = InducedRule(
                candidate.action_name,
                candidate.param_vars,
                candidate.state_pos,
                candidate.goal_pos,
                candidate.goal_neg + [lit],
            )
            got = groundings(trial, state, goal)
            score = (len(got), 0 if got == [action] else 1)
            if got and (best_score is None or score < best_score):
                best = ("neg", lit)
                best_score = score
        if best is None:
            return None if not ok(candidate) else candidate
        kind, lit = best
        if kind == "state":
            candidate.state_pos.append(lit)
            remaining.remove(lit)
        else:
            candidate.goal_neg.append(lit)
            neg_remaining.remove(lit)
    return candidate if ok(candidate) else None


def _minimize_state(rule, state, goal, action):
    required = set(lifted_preconditions(rule.action_name, rule.param_vars))
    changed = True
    while changed:
        changed = False
        for lit in list(rule.state_pos):
            if lit in required:
                continue
            trial = InducedRule(
                rule.action_name,
                rule.param_vars,
                [item for item in rule.state_pos if item != lit],
                rule.goal_pos,
                rule.goal_neg,
            )
            if groundings(trial, state, goal) == [action]:
                rule.state_pos = trial.state_pos
                changed = True
    changed = True
    while changed:
        changed = False
        for lit in list(rule.goal_neg):
            trial = InducedRule(
                rule.action_name,
                rule.param_vars,
                rule.state_pos,
                rule.goal_pos,
                [item for item in rule.goal_neg if item != lit],
            )
            if groundings(trial, state, goal) == [action]:
                rule.goal_neg = trial.goal_neg
                changed = True
    return rule


def _add_condition_to_rule(rule, state, goal, action, rules, traces):
    objects = _related_objects(state, set(action[1]))
    for _pred, args in goal:
        objects |= set(args)
    objects = _related_objects(state, objects)
    permanent = _permanent_goal_atom(state, goal, [action], action)
    gatom = permanent[1] if permanent is not None else None
    mapping = _var_map(action, gatom, objects)
    state_pool = [lit for lit in _lift_state_pool(state, objects, mapping) if lit not in rule.state_pos]
    goal_pool = [
        lit for lit in _lift_complete_goal(goal, objects, mapping, gatom) if lit not in rule.goal_pos
    ]
    others = [item for item in rules if item is not rule]
    for lit in state_pool + goal_pool:
        if lit in state_pool:
            trial = InducedRule(
                rule.action_name, rule.param_vars, rule.state_pos + [lit], list(rule.goal_pos), list(rule.goal_neg)
            )
        else:
            trial = InducedRule(
                rule.action_name, rule.param_vars, list(rule.state_pos), rule.goal_pos + [lit], list(rule.goal_neg)
            )
        trial.confirmations = rule.confirmations
        got = groundings(trial, state, goal)
        if got and got != [action] and got == groundings(rule, state, goal):
            continue
        if not _consistent(trial, traces):
            continue
        if _conflicts_with_library(trial, others, traces):
            continue
        if got == [action] or got == []:
            if lit in state_pool:
                rule.state_pos = trial.state_pos
            else:
                rule.goal_pos = trial.goal_pos
            return True
    return False


def _add_condition_exclude(rule, state, goal, action, traces):
    binding = {var: obj for var, obj in zip(rule.param_vars, action[1])}
    pool = []
    for pred, args in sorted(set(state) | set(goal)):
        if len(args) != len(rule.param_vars):
            continue
        lit = (pred, tuple(rule.param_vars))
        if lit in rule.state_pos:
            continue
        try:
            if _ground(lit, binding) in state:
                continue
        except KeyError:
            continue
        pool.append(lit)
    for lit in pool:
        trial = InducedRule(
            rule.action_name, rule.param_vars, rule.state_pos + [lit], list(rule.goal_pos), list(rule.goal_neg)
        )
        trial.confirmations = rule.confirmations
        if groundings(trial, state, goal):
            continue
        if not _consistent(trial, traces):
            continue
        rule.state_pos = trial.state_pos
        return True
    return False


def _edit_ok(original, trial, rules, traces):
    if not _consistent(trial, traces):
        return False
    for state, goal, action in traces:
        before = groundings(original, state, goal)
        after = groundings(trial, state, goal)
        if after and after != [action]:
            return False
        if before == [action] and after != [action]:
            return False
    replaced = [trial if rule is original else rule for rule in rules]
    return _library_ok_on_traces(replaced, traces)


def _library_ok_on_traces(rules, traces):
    for state, goal, action in traces:
        found = []
        for rule in rules:
            for act in groundings(rule, state, goal):
                found.append(act)
        if len(found) > 1:
            return False
        if len(found) == 1 and found[0] != action:
            return False
    return True


def _consistent(rule, traces):
    for state, goal, action in traces:
        matched = groundings(rule, state, goal)
        if not matched:
            continue
        if matched != [action]:
            return False
    return True


def _conflicts_with_library(rule, rules, traces):
    for state, goal, action in traces:
        new_matches = groundings(rule, state, goal)
        if not new_matches:
            continue
        if new_matches != [action]:
            return True
        for existing in rules:
            if groundings(existing, state, goal):
                return True
    return False


def _permanent_goal_atom(state, goal, plan, action):
    current = frozenset(state)
    first = {}
    after = []
    for index, step in enumerate(plan):
        current = apply(current, step)
        after.append(current)
        for atom in goal:
            if atom in current and atom not in first:
                first[atom] = index
    candidates = []
    for atom, index in first.items():
        if all(atom in step_state for step_state in after[index:]):
            candidates.append((index, atom))
    if not candidates:
        return None
    added = add_effects(action)
    preferred = [item for item in candidates if item[1] in added]
    chosen = preferred if preferred else candidates
    chosen.sort()
    return chosen[0]


def _related_objects(state, seed):
    objects = set(seed)
    changed = True
    while changed:
        changed = False
        for _pred, args in state:
            if not args:
                continue
            if set(args) & objects and not set(args) <= objects:
                objects |= set(args)
                changed = True
    return objects


def _var_map(action, gatom, objects):
    ordered = []
    for arg in action[1]:
        if arg not in ordered:
            ordered.append(arg)
    if gatom is not None:
        for arg in gatom[1]:
            if arg not in ordered:
                ordered.append(arg)
    for arg in sorted(objects):
        if arg not in ordered:
            ordered.append(arg)
    return {obj: f"?x{i}" for i, obj in enumerate(ordered)}


def _lift_state_pool(state, objects, mapping):
    pool = []
    for pred, args in state:
        if not args:
            pool.append((pred, ()))
        elif set(args) <= objects:
            pool.append((pred, tuple(mapping[arg] for arg in args)))
    return sorted(set(pool))


def _rule_vars(rule):
    variables = set(rule.param_vars)
    for pred, args in rule.state_pos + rule.goal_pos + rule.goal_neg:
        variables.update(args)
    return variables


def _holds(rule, state, goal, binding):
    for literal in rule.state_pos:
        if _ground(literal, binding) not in state:
            return False
    for literal in rule.goal_pos:
        if _ground(literal, binding) not in goal:
            return False
    for literal in rule.goal_neg:
        if _ground(literal, binding) in goal:
            return False
    return True


def _ground(literal, binding):
    pred, args = literal
    return (pred, tuple(binding[arg] for arg in args))


def _bindings(variables, blocks):
    variables = list(variables)
    if not variables:
        yield {}
        return
    blocks = list(blocks)

    def rec(index, used, binding):
        if index == len(variables):
            yield dict(binding)
            return
        var = variables[index]
        for block in blocks:
            if block in used:
                continue
            binding[var] = block
            used.add(block)
            yield from rec(index + 1, used, binding)
            used.remove(block)
            del binding[var]

    yield from rec(0, set(), {})


def _blocks(state, goal):
    names = set()
    for pred, args in set(state) | set(goal):
        names.update(args)
    return sorted(names)
