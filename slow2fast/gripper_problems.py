"""Gripper problem generator (the only Gripper-specific code). Emits atoms for slow2fast.pddl.problem_from_atoms,
so every problem reaches the system as parsed PDDL, exactly like a hand-written file.

A problem: some rooms, balls and grippers; the robot starts in one room, every gripper free, each ball in
some room; the goal puts some balls in given rooms. Names are fresh random letters per problem, so rules
can never rely on a name.
"""

import random
import string

from slow2fast.pddl import problem_from_atoms


def _names(rng, prefix, kind, count):
    letters = list(string.ascii_lowercase)
    rng.shuffle(letters)
    return [f"{prefix}{kind}{letters[i]}" for i in range(count)]


def make(domain, name, rng, rooms, balls, grippers, prefix="t", robot_room=None, ball_rooms=None,
         goal_rooms=None, goal_balls=None, save_to=None):
    """Build one problem. Unspecified placements are random.

    ball_rooms / goal_rooms: lists of room indices per ball. goal_balls: indices of balls with a goal
    (default all). A ball whose goal room equals its start room is already satisfied.
    """
    R = _names(rng, prefix, "r", rooms)
    B = _names(rng, prefix, "b", balls)
    G = _names(rng, prefix, "g", grippers)
    robot = R[robot_room if robot_room is not None else rng.randrange(rooms)]
    where = [R[i] for i in (ball_rooms or [rng.randrange(rooms) for _ in B])]
    dest = [R[i] for i in (goal_rooms or [rng.randrange(rooms) for _ in B])]
    chosen = range(balls) if goal_balls is None else goal_balls
    init = {("at-robby", (robot,))}
    init |= {("at", (b, r)) for b, r in zip(B, where)}
    init |= {("free", (g,)) for g in G}
    goal = {("at", (B[i], dest[i])) for i in chosen}
    types = {**{r: "room" for r in R}, **{b: "ball" for b in B}, **{g: "gripper" for g in G}}
    return problem_from_atoms(domain, name, types, init, goal, save_to=save_to)


def _differ(rng, rooms):
    a = rng.randrange(rooms)
    return a, rng.choice([r for r in range(rooms) if r != a])


# ---- stage 1: a handful of rules --------------------------------------------------------------
def stage1(domain, rng, count, prefix="t"):
    """Two rooms, one ball, two grippers. The ball is where the robot is and must go to the other room:
    the plan is pick, move, drop."""
    out = []
    for i in range(count):
        a, b = _differ(rng, 2)
        out.append(make(domain, f"{prefix}s1-{i}", rng, 2, 1, 2, prefix, robot_room=a, ball_rooms=[a], goal_rooms=[b]))
    return out


# ---- stage 2: a deliberate curriculum ---------------------------------------------------------
def stage2(domain, rng, per_phase=3, prefix="t"):
    """Phases, each taught `per_phase` times: (single) as stage 1; (fetch) the robot is in the wrong room;
    (two) two balls, shared and separate goals; (idle) some balls already home; (rooms) three rooms;
    (grippers) one and three grippers."""
    P, out = prefix, []

    def add(phase, i, **kw):
        out.append((phase, make(domain, f"{P}{phase}-{len(out)}", rng, prefix=P, **kw)))

    for i in range(per_phase):
        a, b = _differ(rng, 2)
        add("single", i, rooms=2, balls=1, grippers=2, robot_room=a, ball_rooms=[a], goal_rooms=[b])
    for i in range(per_phase):
        a, b = _differ(rng, 2)
        add("fetch", i, rooms=2, balls=1, grippers=2, robot_room=a, ball_rooms=[b], goal_rooms=[a if i % 2 else b])
    for i in range(per_phase):
        a, b = _differ(rng, 2)
        add("two", i, rooms=2, balls=2, grippers=2, robot_room=a, ball_rooms=[a, a], goal_rooms=[b, b])
    for i in range(per_phase):
        a, b = _differ(rng, 2)
        add("two-split", i, rooms=2, balls=2, grippers=2, robot_room=a, ball_rooms=[a, b], goal_rooms=[b, a])
    for i in range(per_phase):
        a, b = _differ(rng, 2)
        add("idle", i, rooms=2, balls=2, grippers=2, robot_room=a, ball_rooms=[a, b], goal_rooms=[b, b])
    for i in range(per_phase):
        add("rooms3", i, rooms=3, balls=rng.choice([1, 2]), grippers=2)
    for g in (1, 3):
        for i in range(per_phase):
            a, b = _differ(rng, 2)
            add(f"grip{g}", i, rooms=2, balls=2 if g == 1 else 3, grippers=g, robot_room=a,
                ball_rooms=[a] * (2 if g == 1 else 3), goal_rooms=[b] * (2 if g == 1 else 3))
    return out


# ---- stage 3: the general distribution --------------------------------------------------------
def random_problem(domain, name, rng, max_rooms=3, max_balls=4, max_grippers=2, prefix="t"):
    rooms = rng.randint(2, max_rooms)
    balls = rng.randint(1, max_balls)
    grippers = rng.randint(1, max_grippers)
    k = rng.randint(1, balls)
    goal_balls = sorted(rng.sample(range(balls), k))
    return make(domain, name, rng, rooms, balls, grippers, prefix, goal_balls=goal_balls)


def stage3_train(domain, seed, random_count=100, prefix="t", **sizes):
    rng = random.Random(seed)
    lessons = [p for _phase, p in stage2(domain, rng, prefix=prefix)]
    lessons += [random_problem(domain, f"{prefix}rand-{i}", rng, prefix=prefix, **sizes) for i in range(random_count)]
    return lessons


def holdout(domain, seed, count=100, prefix="h", **sizes):
    rng = random.Random(seed + 10**6 + 17)
    return [random_problem(domain, f"{prefix}{i}", rng, prefix=prefix, **sizes) for i in range(count)]
