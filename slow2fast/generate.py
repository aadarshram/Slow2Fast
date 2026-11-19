"""Random multi-tower blocksworld problems, and the curriculum used to train System 1."""

import itertools
import random
import string

from slow2fast.blocksworld import Problem, complete_goal, state_from_towers

S2_REASONS = ("no_match", "multi_match", "below_threshold", "loop_cut")


def make_problem(phase, heights=None, n=4, seed=0, name_prefix="b"):
    """Build one problem in a named curriculum phase."""
    rng = random.Random(seed)
    if phase == "single":
        if heights is None:
            heights = [rng.randint(2, max(2, n))]
        if len(heights) != 1:
            raise ValueError("single phase expects one tower height")
        if heights[0] < 1:
            raise ValueError("height must be >= 1")
        return _all_on_table(heights, rng, name_prefix)
    if phase == "multi":
        if heights is None:
            heights = _random_heights(rng, n, min_towers=2)
        if len(heights) < 2:
            raise ValueError("multi phase expects at least two towers")
        return _all_on_table(heights, rng, name_prefix)
    if phase == "partial":
        if heights is None:
            heights = _random_heights(rng, n, min_towers=1)
        return _partial_toward(heights, rng, name_prefix)
    if phase == "random":
        return random_problem(n=n, seed=seed, name_prefix=name_prefix)
    raise ValueError(f"unknown phase: {phase}")


def random_problem(n=4, seed=0, name_prefix="b"):
    """Sample <=n blocks, random valid init, complete multi-tower goal."""
    if n < 1:
        raise ValueError("n must be >= 1")
    rng = random.Random(seed)
    count = rng.randint(1, n)
    blocks = _fresh_names(count, name_prefix, rng)
    goal_heights = _partition(count, rng)
    goal_towers = _assign_towers(blocks, goal_heights, rng)
    init_heights = _partition(count, rng)
    init_towers = _assign_towers(blocks, init_heights, rng)
    # Shuffle within-tower order relative to goal so init is not always the goal.
    if rng.random() < 0.5:
        init_towers = [list(reversed(tower)) if len(tower) > 1 and rng.random() < 0.5 else tower for tower in init_towers]
    return Problem(blocks, state_from_towers(init_towers), complete_goal(goal_towers))


def train_curriculum(
    n=4,
    practice=2,
    seed=0,
    max_height=None,
    random_count=None,
    name_prefix="t",
):
    """Ordered lessons: single -> multi -> partial -> random.

    practice is the confirmation threshold style repeat count: each new shape
    is shown practice+1 times (create, confirm, then one practiced pass).
    random_count defaults to 100.
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    max_height = max_height or n
    random_count = 100 if random_count is None else random_count
    rng = random.Random(seed)
    lessons = []
    counter = itertools.count(1)

    def add(phase, problem):
        lessons.append((phase, f"{phase}-{next(counter)}", problem))

    # 1) All on table, single tower, growing height.
    for height in range(1, max_height + 1):
        repeats = practice + 1 if height >= 2 else 1
        for _ in range(repeats):
            add("single", make_problem("single", heights=[height], seed=rng.randint(0, 10**9), name_prefix=name_prefix))

    # 2) All on table, multi towers.
    multi_shapes = []
    if n >= 2:
        multi_shapes.append([1, 1] if n == 2 else [2, 1])
    if n >= 3:
        multi_shapes.append([2, 2] if n >= 4 else [2, 1])
    if n >= 4:
        multi_shapes.append([3, 2] if n >= 5 else [2, 1, 1])
    if not multi_shapes:
        multi_shapes = [[1, 1]]
    for shape in multi_shapes:
        if sum(shape) > n:
            continue
        for _ in range(practice + 1):
            add("multi", make_problem("multi", heights=shape, seed=rng.randint(0, 10**9), name_prefix=name_prefix))

    # 3) Partial towers toward a complete multi-tower goal.
    partial_shapes = multi_shapes[:2] or [[max_height]]
    for shape in partial_shapes:
        if sum(shape) > n:
            shape = _random_heights(rng, min(n, sum(shape)), min_towers=1)
        for _ in range(practice + 1):
            add("partial", make_problem("partial", heights=shape, seed=rng.randint(0, 10**9), name_prefix=name_prefix))

    # 4) Fully random init and complete goal.
    for _ in range(random_count):
        add("random", random_problem(n=n, seed=rng.randint(0, 10**9), name_prefix=name_prefix))

    return lessons


def test_holdout(n=4, seed=0, count=None, name_prefix="h"):
    """Fresh random tasks for a frozen test pass. count defaults to 100."""
    if n < 1:
        raise ValueError("n must be >= 1")
    count = 100 if count is None else count
    if count < 0:
        raise ValueError("count must be >= 0")
    # Offset the seed stream so holdout tasks are not the train random tail.
    rng = random.Random(seed + 10**6 + 17)
    lessons = []
    for index in range(1, count + 1):
        problem = random_problem(n=n, seed=rng.randint(0, 10**9), name_prefix=name_prefix)
        lessons.append(("random", f"random-{index}", problem))
    return lessons


def _all_on_table(heights, rng, name_prefix):
    if not heights:
        raise ValueError("heights must be non-empty")
    if any(h < 1 for h in heights):
        raise ValueError("heights must be >= 1")
    count = sum(heights)
    blocks = _fresh_names(count, name_prefix, rng)
    towers = _assign_towers(blocks, heights, rng)
    initial = state_from_towers([[block] for block in blocks])
    return Problem(blocks, initial, complete_goal(towers))


def _partial_toward(heights, rng, name_prefix):
    """Goal is complete towers; init keeps a proper prefix of some towers stacked."""
    if not heights:
        raise ValueError("heights must be non-empty")
    count = sum(heights)
    blocks = _fresh_names(count, name_prefix, rng)
    goal_towers = _assign_towers(blocks, heights, rng)
    init_towers = []
    leftovers = []
    made_partial = False
    for tower in goal_towers:
        if len(tower) == 1:
            leftovers.append(tower[0])
            continue
        # Keep a non-empty proper prefix stacked (from the base up).
        keep = rng.randint(1, len(tower) - 1)
        fragment = list(tower[len(tower) - keep :])
        init_towers.append(fragment)
        leftovers.extend(tower[: len(tower) - keep])
        made_partial = True
    if not made_partial:
        # All height-1: stack two leftovers wrongly if possible, else leave on table.
        if len(leftovers) >= 2:
            top, support = leftovers[0], leftovers[1]
            init_towers.append([top, support])
            leftovers = leftovers[2:]
            made_partial = True
    init_towers.extend([[block] for block in leftovers])
    if not made_partial and init_towers:
        # Force at least one on-atom by stacking two singletons if present.
        singles = [t[0] for t in init_towers if len(t) == 1]
        if len(singles) >= 2:
            rest = [t for t in init_towers if len(t) != 1]
            init_towers = rest + [[singles[0], singles[1]]] + [[b] for b in singles[2:]]
    return Problem(blocks, state_from_towers(init_towers), complete_goal(goal_towers))


def _random_heights(rng, n, min_towers=1):
    if n < 1:
        raise ValueError("n must be >= 1")
    min_towers = max(1, min(min_towers, n))
    return _partition(n, rng, min_parts=min_towers)


def _partition(n, rng, min_parts=1):
    """Random partition of n into parts >= 1."""
    if n < 1:
        raise ValueError("n must be >= 1")
    min_parts = max(1, min(min_parts, n))
    cuts = sorted(rng.sample(range(1, n), min_parts - 1)) if min_parts > 1 else []
    # Add more random cuts sometimes.
    extra = rng.randint(0, max(0, n - 1 - len(cuts)))
    choices = [i for i in range(1, n) if i not in cuts]
    cuts = sorted(cuts + rng.sample(choices, extra)) if extra and choices else cuts
    parts = []
    prev = 0
    for cut in cuts + [n]:
        parts.append(cut - prev)
        prev = cut
    rng.shuffle(parts)
    return parts


def _assign_towers(blocks, heights, rng):
    blocks = list(blocks)
    rng.shuffle(blocks)
    towers = []
    index = 0
    for height in heights:
        towers.append(blocks[index : index + height])
        index += height
    if index != len(blocks):
        raise ValueError("heights do not cover blocks")
    return towers


def _fresh_names(count, prefix, rng):
    alphabet = string.ascii_lowercase
    names = []
    i = 0
    while len(names) < count:
        if i < len(alphabet):
            names.append(f"{prefix}{alphabet[i]}")
        else:
            names.append(f"{prefix}{i}")
        i += 1
    rng.shuffle(names)
    return names[:count]
