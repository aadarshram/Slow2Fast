"""Checkpoint 2: five lifted cues learned from the task sequence, then a frozen block."""

import json
from pathlib import Path

from slow2fast.blocksworld import Tower, apply, goal_holds, initial_state
from slow2fast.episode import EpisodeResult, Step
from slow2fast.planner import search

SCHEMAS = ("pickup-base", "pickup-next", "stack", "unstack", "putdown")


class SkillLibrary:
    """known_rules=True keeps the hand schemas. Default induces rules from traces."""

    def __init__(self, threshold=2, known_rules=False):
        self.known_rules = known_rules
        if known_rules:
            self._impl = _KnownSkillLibrary(threshold)
        else:
            from slow2fast.induce import InducedLibrary

            self._impl = InducedLibrary(threshold)

    def counts(self):
        return self._impl.counts()

    def propose(self, state, goal):
        return self._impl.propose(state, goal)

    def diagnose(self, state, goal):
        return self._impl.diagnose(state, goal)

    def observe(self, state, goal, action, plan=None):
        if self.known_rules:
            return self._impl.observe(state, goal, action)
        return self._impl.observe(state, goal, action, plan=plan)

    def note_success(self, name):
        return self._impl.note_success(name)

    @property
    def rules(self):
        return getattr(self._impl, "rules", [])

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if self.known_rules:
            payload = {
                "known_rules": True,
                "threshold": self._impl.threshold,
                "confirmations": dict(self._impl.confirmations),
            }
        else:
            payload = {
                "known_rules": False,
                "threshold": self._impl.threshold,
                "rules": [_dump_induced_rule(rule) for rule in self._impl.rules],
            }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    @classmethod
    def load(cls, path):
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"saved rules not found: {path}")
        payload = json.loads(path.read_text())
        known = bool(payload.get("known_rules", False))
        threshold = int(payload.get("threshold", 2))
        library = cls(threshold=threshold, known_rules=known)
        if known:
            counts = payload.get("confirmations", {})
            for name in SCHEMAS:
                library._impl.confirmations[name] = int(counts.get(name, 0))
            return library
        from slow2fast.induce import InducedRule

        library._impl.rules = []
        for raw in payload.get("rules", []):
            rule = InducedRule(
                raw["action_name"],
                tuple(raw["param_vars"]),
                [_load_atom(atom) for atom in raw.get("state_pos", [])],
                [_load_atom(atom) for atom in raw.get("goal_pos", [])],
                [_load_atom(atom) for atom in raw.get("goal_neg", [])],
            )
            rule.confirmations = int(raw.get("confirmations", 0))
            library._impl.rules.append(rule)
        return library


def _dump_atom(atom):
    pred, args = atom
    return [pred, list(args)]


def _load_atom(raw):
    pred, args = raw
    return (pred, tuple(args))


def _dump_induced_rule(rule):
    return {
        "action_name": rule.action_name,
        "param_vars": list(rule.param_vars),
        "state_pos": [_dump_atom(atom) for atom in rule.state_pos],
        "goal_pos": [_dump_atom(atom) for atom in rule.goal_pos],
        "goal_neg": [_dump_atom(atom) for atom in rule.goal_neg],
        "confirmations": int(rule.confirmations),
    }


class _KnownSkillLibrary:
    def __init__(self, threshold=2):
        self.threshold = threshold
        self.confirmations = {name: 0 for name in SCHEMAS}

    def counts(self):
        return dict(self.confirmations)

    def propose(self, state, goal):
        found = []
        for name in SCHEMAS:
            if self.confirmations[name] < self.threshold:
                continue
            found.extend(matches(name, state, goal))
        if len(found) == 1:
            name, action, _binding = found[0]
            return name, action
        return None

    def diagnose(self, state, goal):
        practiced = []
        unpracticed = []
        for name in SCHEMAS:
            hits = [(name, action) for name, action, _binding in matches(name, state, goal)]
            if self.confirmations[name] >= self.threshold:
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

    def observe(self, state, goal, action):
        named = []
        for name in SCHEMAS:
            hits = matches(name, state, goal)
            if len(hits) == 1 and hits[0][1] == action:
                named.append(name)
        if len(named) == 1:
            self.confirmations[named[0]] += 1

    def note_success(self, name):
        self.confirmations[name] += 1


def run_skill_episode(problem, library, update):
    state = frozenset(problem.initial)
    seen = {state}
    result = EpisodeResult()
    bound = 8 * max(1, len(tuple(problem.blocks)))
    while not goal_holds(state, problem.goal) and len(result.steps) < bound:
        proposal = library.propose(state, problem.goal)
        s2_reason = None
        if proposal is not None:
            name, action = proposal
            nxt = apply(state, action)
            if nxt not in seen:
                result.steps.append(Step("s1", action))
                if nxt == apply(state, action):
                    result.s1_ok += 1
                    if update:
                        library.note_success(name)
                else:
                    result.s1_bad += 1
                seen.add(nxt)
                state = nxt
                continue
            s2_reason = "loop_cut"
        else:
            s2_reason, _detail = library.diagnose(state, problem.goal)
        plan = search(state, problem.goal, problem.blocks)
        if not plan:
            break
        action = plan[0]
        nxt = apply(state, action)
        result.steps.append(Step("s2", action, s2_reason=s2_reason))
        result.s2_steps += 1
        if update:
            library.observe(state, problem.goal, action, plan=plan)
        seen.add(nxt)
        state = nxt
    result.goal_reached = goal_holds(state, problem.goal)
    return result


def matches(name, state, goal):
    state = set(state)
    goal = set(goal)
    blocks = _blocks(state, goal)
    found = []
    if name == "pickup-base":
        if ("handempty", ()) not in state:
            return found
        for top in blocks:
            for support in blocks:
                if top == support:
                    continue
                if _pickup_base(state, goal, top, support):
                    found.append((name, ("pickup", (top,)), (top, support)))
    elif name == "pickup-next":
        if ("handempty", ()) not in state:
            return found
        for top in blocks:
            for support in blocks:
                for under in blocks:
                    if len({top, support, under}) < 3:
                        continue
                    if _pickup_next(state, goal, top, support, under):
                        found.append((name, ("pickup", (top,)), (top, support, under)))
    elif name == "stack":
        for top in blocks:
            for support in blocks:
                if top == support:
                    continue
                if _stack(state, goal, top, support):
                    found.append((name, ("stack", (top, support)), (top, support)))
    elif name == "unstack":
        if ("handempty", ()) not in state:
            return found
        for top in blocks:
            for support in blocks:
                if top == support:
                    continue
                if _unstack(state, goal, top, support):
                    found.append((name, ("unstack", (top, support)), (top, support)))
    elif name == "putdown":
        for block in blocks:
            if _putdown(state, goal, block):
                found.append((name, ("putdown", (block,)), (block,)))
    return found


def _pickup_base(state, goal, top, support):
    return (
        ("clear", (top,)) in state
        and ("ontable", (top,)) in state
        and ("clear", (support,)) in state
        and ("ontable", (support,)) in state
        and ("on", (top, support)) in goal
        and _is_base(support, goal)
    )


def _pickup_next(state, goal, top, support, under):
    return (
        ("clear", (top,)) in state
        and ("ontable", (top,)) in state
        and ("clear", (support,)) in state
        and ("on", (support, under)) in state
        and ("on", (support, under)) in goal
        and ("on", (top, support)) in goal
    )


def _stack(state, goal, top, support):
    return ("holding", (top,)) in state and ("clear", (support,)) in state and ("on", (top, support)) in goal


def _unstack(state, goal, top, support):
    return (
        ("clear", (top,)) in state
        and ("on", (top, support)) in state
        and ("on", (top, support)) not in goal
    )


def _putdown(state, goal, block):
    if ("holding", (block,)) not in state:
        return False
    return not any(pred == "on" and args[0] == block for pred, args in goal)


def _is_base(block, goal):
    tops = {args[0] for pred, args in goal if pred == "on"}
    supports = {args[1] for pred, args in goal if pred == "on"}
    return block in supports and block not in tops


def _blocks(state, goal):
    names = set()
    for pred, args in set(state) | set(goal):
        names.update(args)
    return sorted(names)


def invert(upper, lower):
    """upper starts on lower. The goal is lower on upper."""
    problem = Tower([lower, upper])
    state = set(initial_state([upper, lower]))
    state.remove(("ontable", (upper,)))
    state.remove(("clear", (lower,)))
    state.add(("on", (upper, lower)))
    problem.initial = frozenset(state)
    return problem


def sunk_support():
    """a is already on b, and b still has to move onto c."""
    from slow2fast.blocksworld import Problem, complete_goal, state_from_towers

    blocks = ("a", "b", "c")
    initial = state_from_towers([["a", "b"], ["c"]])
    goal = complete_goal([["a", "b", "c"]])
    return Problem(blocks, initial, goal)


LESSONS = (
    ("h2-1", Tower(["a", "b"])),
    ("h2-2", Tower(["c", "d"])),
    ("h2-3", Tower(["e", "f"])),
    ("h3-1", Tower(["a", "b", "c"])),
    ("h3-2", Tower(["d", "e", "f"])),
    ("h3-3", Tower(["g", "h", "i"])),
    ("h4", Tower(["w", "x", "y", "z"])),
    ("inv-1", invert("p", "q")),
    ("inv-2", invert("r", "s")),
    ("inv-3", invert("t", "u")),
)

FINALS = (
    ("final-h2", Tower(["m", "n"])),
    ("final-h3", Tower(["m", "n", "o"])),
    ("final-h4", Tower(["m", "n", "o", "p"])),
    ("final-inv", invert("m", "n")),
)
