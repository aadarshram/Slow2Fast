"""Execute one tower. A practiced stack rule may act; otherwise the planner does."""

from dataclasses import dataclass, field

from cmc.blocksworld import apply, goal_holds
from cmc.planner import search


@dataclass
class Step:
    source: str
    action: tuple
    s2_reason: str | None = None


@dataclass
class EpisodeResult:
    steps: list = field(default_factory=list)
    goal_reached: bool = False
    s1_ok: int = 0
    s1_bad: int = 0
    s2_steps: int = 0


def run_episode(tower, library, update):
    state = frozenset(tower.initial)
    seen = {state}
    result = EpisodeResult()
    bound = 8 * max(1, len(tuple(tower.blocks)))
    while not goal_holds(state, tower.goal) and len(result.steps) < bound:
        proposal = _system1_action(library, state, tower.goal, seen)
        if proposal is not None:
            rule, binding, action, nxt = proposal
            result.steps.append(Step("s1", action))
            if nxt == apply(state, action):
                result.s1_ok += 1
                if update:
                    rule.confirmations += 1
                    rule.record_success(state, binding)
            else:
                result.s1_bad += 1
                if update:
                    library.revise(rule, state, binding)
            seen.add(nxt)
            state = nxt
            continue
        plan = search(state, tower.goal, tower.blocks)
        if not plan:
            break
        action = plan[0]
        nxt = apply(state, action)
        result.steps.append(Step("s2", action))
        result.s2_steps += 1
        if update and action[0] == "stack" and nxt == apply(state, action):
            top, support = action[1]
            library.observe_planner_stack(state, {"?x": top, "?y": support})
        seen.add(nxt)
        state = nxt
    result.goal_reached = goal_holds(state, tower.goal)
    return result


def _system1_action(library, state, goal, seen):
    proposed = library.propose(state, goal)
    if proposed is None:
        return None
    rule, binding = proposed
    action = ("stack", (binding["?x"], binding["?y"]))
    nxt = apply(state, action)
    if nxt in seen:
        return None
    return rule, binding, action, nxt
