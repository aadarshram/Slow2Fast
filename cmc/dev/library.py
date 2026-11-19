"""Lifted stack rules. A rule fires only after two successful uses, and only when one grounding matches."""

STACK_STATE = (("holding", ("?x",)), ("clear", ("?y",)))
STACK_GOAL = (("on", ("?x", "?y")),)


class Rule:
    def __init__(self):
        self.action = "stack"
        self.state_cue = list(STACK_STATE)
        self.goal_cue = list(STACK_GOAL)
        self.confirmations = 0
        self.retired = False
        self.successes = []

    def record_success(self, state, binding):
        self.successes.append((frozenset(state), dict(binding)))


class Library:
    def __init__(self, threshold=2):
        self.threshold = threshold
        self.rules = []

    def confirmation_count(self, name):
        live = [rule.confirmations for rule in self.rules if rule.action == name and not rule.retired]
        if not live:
            return 0
        return max(live)

    def only_rule(self):
        return self.rules[-1]

    def add_practiced_stack(self):
        rule = Rule()
        rule.confirmations = self.threshold
        self.rules.append(rule)
        return rule

    def propose(self, state, goal):
        found = []
        for rule in self.rules:
            if rule.retired or rule.confirmations < self.threshold:
                continue
            for binding in _pair_bindings(state):
                if _cue_holds(rule, state, goal, binding):
                    found.append((rule, binding))
        if len(found) == 1:
            return found[0]
        return None

    def observe_planner_stack(self, state, binding):
        matched = [
            rule
            for rule in self.rules
            if not rule.retired and _cue_holds(rule, state, _goal_from_binding(binding), binding)
        ]
        if len(matched) == 1:
            matched[0].confirmations += 1
            matched[0].record_success(state, binding)
            return
        if matched:
            return
        rule = Rule()
        rule.confirmations = 1
        rule.record_success(state, binding)
        self.rules.append(rule)

    def revise(self, rule, failed_state, binding):
        extra = _separating_literals(rule, failed_state, binding)
        if len(extra) == 1:
            rule.state_cue.append(extra[0])
            return
        rule.retired = True


def _goal_from_binding(binding):
    return frozenset({("on", (binding["?x"], binding["?y"]))})


def _pair_bindings(state):
    blocks = sorted({arg for _pred, args in state for arg in args})
    for top in blocks:
        for support in blocks:
            if top != support:
                yield {"?x": top, "?y": support}


def _ground(literal, binding):
    pred, args = literal
    return (pred, tuple(binding.get(arg, arg) for arg in args))


def _cue_holds(rule, state, goal, binding):
    state = set(state)
    goal = set(goal)
    return all(_ground(literal, binding) in state for literal in rule.state_cue) and all(
        _ground(literal, binding) in goal for literal in rule.goal_cue
    )


def _separating_literals(rule, failed_state, binding):
    if not rule.successes:
        return []
    already = set(rule.state_cue) | set(rule.goal_cue)
    candidates = set()
    for state, success_binding in rule.successes:
        candidates.update(_lifted_atoms(state, success_binding, owned_values(success_binding)))
    kept = []
    for literal in sorted(candidates):
        if literal in already:
            continue
        true_of_successes = all(
            _ground(literal, success_binding) in set(state) for state, success_binding in rule.successes
        )
        false_of_failure = _ground(literal, binding) not in set(failed_state)
        if true_of_successes and false_of_failure:
            kept.append(literal)
    return kept


def owned_values(binding):
    return set(binding.values())


def _lifted_atoms(state, binding, owned):
    inverse = {block: var for var, block in binding.items()}
    lifted = set()
    for pred, args in state:
        if any(arg not in owned for arg in args):
            continue
        if any(arg not in inverse for arg in args):
            continue
        lifted.add((pred, tuple(inverse[arg] for arg in args)))
    return lifted
