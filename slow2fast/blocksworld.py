"""Blocksworld problem helpers (towers, complete goals) and thin wrappers over the PDDL-derived operators.

Predicates used in states and complete goals:
  on(x, y), ontable(x), clear(x), handempty, holding(x)
"""

from slow2fast.domain import DOMAIN, OPERATORS, ground_ops

PREDICATES = ("on", "ontable", "clear", "handempty", "holding")


def initial_state(blocks):
    state = {("handempty", ())}
    for block in blocks:
        state.add(("ontable", (block,)))
        state.add(("clear", (block,)))
    return frozenset(state)


def goal_holds(state, goal):
    return set(goal) <= set(state)


def predicates_in(atoms):
    return {pred for pred, _args in atoms}


def complete_goal(towers, handempty=True):
    """Complete goal for a list of towers.

    Each tower is top-to-base, e.g. ["a", "b", "c"] means a on b on c on table.
    Height-1 towers contribute ontable and clear only.
    """
    goal = set()
    if handempty:
        goal.add(("handempty", ()))
    seen = set()
    for tower in towers:
        if not tower:
            raise ValueError("empty tower")
        tower = tuple(tower)
        for block in tower:
            if block in seen:
                raise ValueError(f"block appears in two towers: {block}")
            seen.add(block)
        for top, support in zip(tower, tower[1:]):
            goal.add(("on", (top, support)))
        goal.add(("ontable", (tower[-1],)))
        goal.add(("clear", (tower[0],)))
    return frozenset(goal)


def state_from_towers(towers, holding=None):
    """Build a valid state from towers (top-to-base) and optional held block."""
    state = set()
    seen = set()
    if holding is not None:
        seen.add(holding)
        state.add(("holding", (holding,)))
    else:
        state.add(("handempty", ()))
    for tower in towers:
        if not tower:
            raise ValueError("empty tower")
        tower = tuple(tower)
        for block in tower:
            if block in seen:
                raise ValueError(f"block appears twice in state: {block}")
            seen.add(block)
        for top, support in zip(tower, tower[1:]):
            state.add(("on", (top, support)))
        state.add(("ontable", (tower[-1],)))
        state.add(("clear", (tower[0],)))
    return frozenset(state)


class Problem:
    """A blocksworld instance: blocks, initial state, goal."""

    def __init__(self, blocks, initial, goal):
        self.blocks = tuple(blocks)
        self.names = self.blocks
        self.initial = frozenset(initial)
        self.goal = frozenset(goal)


class Tower(Problem):
    """All blocks on the table; goal stacks names[0] on names[1] on ... on table."""

    def __init__(self, names):
        names = tuple(names)
        if not names:
            raise ValueError("tower needs at least one block")
        initial = initial_state(names)
        goal = complete_goal([names])
        super().__init__(names, initial, goal)


def apply(state, action):
    name, args = action
    if name not in OPERATORS:
        raise ValueError(f"unknown action: {action}")
    if name == "stack" and len(args) == 2 and args[0] == args[1]:
        raise ValueError(f"stack is not applicable: {action}")
    needed, add, delete = ground_ops(action)
    state = set(state)
    if not needed <= state:
        raise ValueError(f"{name} is not applicable: {action}")
    state -= delete
    state |= add
    return frozenset(state)


def applicable_actions(state, blocks):
    """Ground actions applicable in `state`, from the PDDL-derived operator model."""
    return DOMAIN.applicable_actions(state, blocks)
