"""System 2: enforced hill-climbing. It does not read the rule set."""

from collections import deque

from slow2fast.blocksworld import applicable_actions, apply, goal_holds


def search(state, goal, blocks, depth_factor=8):
    """Return the first satisficing plan, or None inside the depth bound.

    Enforced hill-climbing (Hoffmann and Nebel, 2001). Breadth-first search
    runs only until some state has fewer missing goal atoms. That path is kept,
    and the climb repeats from there. A state visited twice is a detour: those
    steps are cut, and the first remaining action is the one to take.
    """
    if goal_holds(state, goal):
        return []
    start = frozenset(state)
    bound = depth_factor * max(1, len(tuple(blocks)))
    current = start
    missing = _missing(current, goal)
    plan = []
    while missing:
        path = _closer_path(current, goal, blocks, missing, bound - len(plan))
        if path is None:
            return None
        for action in path:
            current = apply(current, action)
            plan.append(action)
        missing = _missing(current, goal)
    # The story visits a state twice. Cut that detour and return what remains.
    return _cut_loops(start, plan)


def _cut_loops(start, plan):
    state = frozenset(start)
    visited = [state]
    kept = []
    for action in plan:
        nxt = apply(state, action)
        if nxt in visited:
            back = visited.index(nxt)
            kept = kept[:back]
            visited = visited[: back + 1]
            state = visited[-1]
        else:
            kept.append(action)
            visited.append(nxt)
            state = nxt
    return kept


def _missing(state, goal):
    """How many goal atoms are not true in this state."""
    return len(set(goal) - set(state))


def _closer_path(state, goal, blocks, missing, room):
    """Nearest state with fewer missing goal atoms than `missing`."""
    if room <= 0:
        return None
    queue = deque([(frozenset(state), ())])
    seen = {frozenset(state)}
    while queue:
        current, plan = queue.popleft()
        if len(plan) >= room:
            continue
        for action in applicable_actions(current, blocks):
            nxt = apply(current, action)
            if nxt in seen:
                continue
            seen.add(nxt)
            extended = plan + (action,)
            if _missing(nxt, goal) < missing:
                return extended
            queue.append((nxt, extended))
    return None
