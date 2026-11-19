"""Problem generators for Barman, Termes and Tidybot (the only domain-specific code for these domains).

Each `make_*` builds one problem from atoms and returns it parsed back from PDDL text, like a hand-written
file. Object names are fresh random letters per problem so a rule can never rely on a name. Generators take
sizes explicitly; the staged curricula and random distributions are below each domain.
"""

import random
import string

from slow2fast.pddl import problem_from_atoms


class Names:
    """Unique random names: a prefix, a one-letter kind tag and random letters."""

    def __init__(self, rng, prefix):
        self.rng, self.prefix, self.used = rng, prefix, set()

    def new(self, kind):
        while True:
            name = f"{self.prefix}{kind}{''.join(self.rng.choice(string.ascii_lowercase) for _ in range(2))}"
            if name not in self.used:
                self.used.add(name)
                return name

    def many(self, kind, count):
        return [self.new(kind) for _ in range(count)]


# =============================== Barman =====================================================
def make_barman(domain, name, rng, shots=2, ingredients=3, cocktails=2, goals=None, prefix="t", levels=3):
    """A two-handed bartender. goals: list of (shot index, cocktail index) pairs with distinct shots.
    Each cocktail is a shaken mix of two distinct ingredients."""
    n = Names(rng, prefix)
    hands, shot, shaker = n.many("h", 2), n.many("s", shots), n.new("k")
    ingr, disp, cock = n.many("i", ingredients), n.many("d", ingredients), n.many("c", cocktails)
    lev = n.many("l", levels)
    types = {**{h: "hand" for h in hands}, **{s: "shot" for s in shot}, shaker: "shaker",
             **{i: "ingredient" for i in ingr}, **{d: "dispenser" for d in disp},
             **{c: "cocktail" for c in cock}, **{l: "level" for l in lev}}
    init = {("ontable", (shaker,)), ("clean", (shaker,)), ("empty", (shaker,)),
            ("shaker-empty-level", (shaker, lev[0])), ("shaker-level", (shaker, lev[0]))}
    init |= {("handempty", (h,)) for h in hands}
    for s in shot:
        init |= {("ontable", (s,)), ("clean", (s,)), ("empty", (s,))}
    init |= {("next", (lev[i], lev[i + 1])) for i in range(levels - 1)}
    init |= {("dispenses", (d, i)) for d, i in zip(disp, ingr)}
    for c in cock:
        p1, p2 = rng.sample(ingr, 2)
        init |= {("cocktail-part1", (c, p1)), ("cocktail-part2", (c, p2))}
    if goals is None:
        goals = [(i, rng.randrange(cocktails)) for i in rng.sample(range(shots), rng.randint(1, shots))]
    goal = {("contains", (shot[s], cock[c])) for s, c in goals}
    return problem_from_atoms(domain, name, types, init, goal)


# =============================== Termes =====================================================
def make_termes(domain, name, rng, width=2, height=2, targets=None, max_height=1, prefix="t"):
    """A robot builds a structure on a width x height grid, starting at the depot (one corner) with no block.
    targets: dict {(x, y): height}; the goal fixes the height of EVERY non-depot cell (zero included)."""
    n = Names(rng, prefix)
    cells = [(x, y) for x in range(width) for y in range(height)]
    pos = {c: n.new("p") for c in cells}
    depot = rng.choice([(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)])
    nums = n.many("n", max_height + 1)
    types = {**{p: "position" for p in pos.values()}, **{m: "numb" for m in nums}}
    init = {("at", (pos[depot],)), ("no-block", ()), ("is-depot", (pos[depot],))}
    init |= {("not-depot", (pos[c],)) for c in cells if c != depot}
    init |= {("height", (pos[c], nums[0])) for c in cells}
    init |= {("succ", (nums[i + 1], nums[i])) for i in range(max_height)}
    for (x, y) in cells:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + dx, y + dy) in pos:
                init.add(("neighbor", (pos[(x, y)], pos[(x + dx, y + dy)])))
    if targets is None:
        targets = {c: rng.randint(0, max_height) for c in cells if c != depot}
    goal = {("height", (pos[c], nums[targets.get(c, 0)])) for c in cells if c != depot}
    goal.add(("no-block", ()))
    return problem_from_atoms(domain, name, types, init, goal)


# =============================== Tidybot ====================================================
def make_tidybot(domain, name, rng, width=4, height=3, items=1, tables=None, prefix="t", reach=1, extra_tables=0):
    """A household robot on a grid. Tables (base cannot enter, objects can rest on them); items start on
    one table cell each and must end on another, distinct, table cell. The robot starts parked with its
    gripper retracted. `tables` is a list of cells (default: random cells, at least items*2 of them).
    reach: the gripper can extend this far from the base in each direction."""
    n = Names(rng, prefix)
    cells = [(x, y) for x in range(width) for y in range(height)]
    xs, ys = n.many("x", width), n.many("y", height)
    rel = range(-reach, reach + 1)
    xr, yr = {r: n.new("u") for r in rel}, {r: n.new("v") for r in rel}
    robot, item = n.new("r"), n.many("o", items)
    if tables is None:
        k = max(2 * items, 2) + extra_tables
        tables = rng.sample(cells, k)
    floor = [c for c in cells if c not in tables]
    base = rng.choice(floor)
    starts = rng.sample(tables, items)
    goals_ = rng.sample([t for t in tables if t not in starts], items)
    types = {robot: "robot", **{i: "item" for i in item}, **{x: "xc" for x in xs}, **{y: "yc" for y in ys},
             **{v: "xrel" for v in xr.values()}, **{v: "yrel" for v in yr.values()}}
    X = lambda c: xs[c[0]]
    Y = lambda c: ys[c[1]]
    init = {("leftof", (xs[i], xs[i + 1])) for i in range(width - 1)}
    init |= {("above", (ys[i], ys[i + 1])) for i in range(height - 1)}
    init |= {("leftof-rel", (xr[r], xr[r + 1])) for r in rel if r + 1 in xr}
    init |= {("above-rel", (yr[r], yr[r + 1])) for r in rel if r + 1 in yr}
    init |= {("zerox-rel", (xr[0],)), ("zeroy-rel", (yr[0],))}
    init |= {("sum-x", (xs[x], xr[r], xs[x + r])) for x in range(width) for r in rel if 0 <= x + r < width}
    init |= {("sum-y", (ys[y], yr[r], ys[y + r])) for y in range(height) for r in rel if 0 <= y + r < height}
    init |= {("surface", (X(t), Y(t))) for t in tables}
    init |= {("object-goal", (o, X(g), Y(g))) for o, g in zip(item, goals_)}
    init |= {("parked", (robot,)), ("base-pos", (robot, X(base), Y(base))), ("gripper-empty", (robot,)),
             ("gripper-rel", (robot, xr[0], yr[0])), ("not-pushing", (robot,))}
    init |= {("object-pos", (o, X(s), Y(s))) for o, s in zip(item, starts)} | {("object-active", (o,)) for o in item}
    base_blocked = set(tables) | {base}
    grip_blocked = set(starts) | {base}
    init |= {("base-obstacle", (X(c), Y(c))) for c in base_blocked}
    init |= {("base-free", (X(c), Y(c))) for c in cells if c not in base_blocked}
    init |= {("gripper-obstacle", (X(c), Y(c))) for c in grip_blocked}
    init |= {("gripper-free", (X(c), Y(c))) for c in cells if c not in grip_blocked}
    goal = {("object-done", (o,)) for o in item}
    return problem_from_atoms(domain, name, types, init, goal)


# =============================== staged distributions ========================================
# Each domain: `curriculum` = (phase, repeats, kwargs-factory) lessons taught in order (oracle knowledge, as for
# blocksworld and gripper); `random_kwargs` = the general distribution used for the random tail and the frozen
# holdout; `big_kwargs` = larger problems the learner never saw.
def _barman_random(rng, big=False):
    """Goals ask for ONE cocktail type in 1-2 shots. Two different cocktails, or three shots of one cocktail
    (a second shaker cycle), are beyond what pyperplan's hill-climbing plans in reasonable time (tens of
    seconds per plan, many failures). `big` scales ingredients, cocktails and shots instead."""
    shots = rng.choice([3, 4]) if big else rng.choice([2, 3])
    cocktails = rng.randint(3, 4) if big else rng.randint(1, 3)
    ingredients = rng.choice([4, 5]) if big else 3
    count = min(shots, rng.randint(1, 2))
    kind = rng.randrange(cocktails)
    return dict(shots=shots, cocktails=cocktails, ingredients=ingredients,
                goals=[(i, kind) for i in rng.sample(range(shots), count)])


BARMAN_CURRICULUM = [
    ("one-drink", 3, lambda r: dict(shots=2, cocktails=1, goals=[(0, 0)])),
    ("which-cocktail", 3, lambda r: dict(shots=2, cocktails=3, goals=[(0, r.randrange(3))])),
    ("two-same", 3, lambda r: dict(shots=2, cocktails=1, goals=[(0, 0), (1, 0)])),
    ("spare-shots", 3, lambda r: dict(shots=3, cocktails=2, goals=[(1, 0), (2, 0)])),
]


def _termes_random(rng, big=False):
    if big:
        w, h = rng.choice([(3, 4), (4, 3)])
        return dict(width=w, height=h, max_height=1)
    w, h = rng.choice([(2, 2), (2, 3), (3, 2), (3, 3)])
    return dict(width=w, height=h, max_height=rng.choice([1, 1, 2]) if w * h <= 6 else 1)


TERMES_CURRICULUM = [
    ("flat-2x2", 3, lambda r: dict(width=2, height=2, max_height=1)),
    ("flat-2x3", 3, lambda r: dict(width=2, height=3, max_height=1)),
    ("flat-3x3", 3, lambda r: dict(width=3, height=3, max_height=1)),
    ("stairs-2x2", 3, lambda r: dict(width=2, height=2, max_height=2)),
]


def _tidybot_random(rng, big=False):
    if big:
        return dict(width=6, height=4, items=rng.choice([2, 3]), extra_tables=rng.randint(0, 2))
    return dict(width=rng.choice([4, 5]), height=rng.choice([3, 4]), items=rng.choice([1, 1, 2]),
                extra_tables=rng.randint(0, 2))


TIDYBOT_CURRICULUM = [
    ("one-item-4x3", 3, lambda r: dict(width=4, height=3, items=1)),
    ("one-item-5x4", 3, lambda r: dict(width=5, height=4, items=1)),
    ("two-items-5x4", 3, lambda r: dict(width=5, height=4, items=2)),
]

SPECS = {
    "barman": (make_barman, BARMAN_CURRICULUM, _barman_random),
    "termes": (make_termes, TERMES_CURRICULUM, _termes_random),
    "tidybot": (make_tidybot, TIDYBOT_CURRICULUM, _tidybot_random),
}


def _build(maker, domain, name, rng, kwargs, prefix, accept):
    for _ in range(60):
        problem = maker(domain, name, rng, prefix=prefix, **kwargs)
        if accept is None or accept(problem):
            return problem
        kwargs = kwargs() if callable(kwargs) else kwargs
    raise RuntimeError(f"could not generate an acceptable {name}")


def _sample(maker, domain, name, rng, factory, prefix, accept):
    for _ in range(80):
        problem = maker(domain, name, rng, prefix=prefix, **factory(rng))
        if accept is None or accept(problem):
            return problem
    raise RuntimeError(f"could not generate an acceptable {name}")


def curriculum(kind, domain, seed, prefix="t", accept=None):
    maker, lessons, _rand = SPECS[kind]
    rng = random.Random(seed)
    return [(phase, _sample(maker, domain, f"{prefix}{phase}-{i}", rng, factory, prefix, accept))
            for phase, repeats, factory in lessons for i in range(repeats)]


def random_set(kind, domain, seed, count, prefix="t", accept=None, big=False, offset=0):
    maker, _lessons, rand = SPECS[kind]
    rng = random.Random(seed + offset)
    return [_sample(maker, domain, f"{prefix}rand-{i}", rng, lambda r: rand(r, big), prefix, accept)
            for i in range(count)]


def train_set(kind, domain, seed, random_count=60, accept=None):
    lessons = [p for _ph, p in curriculum(kind, domain, seed, "t", accept)]
    return lessons + random_set(kind, domain, seed + 1, random_count, "t", accept)


def holdout_set(kind, domain, seed, count=40, accept=None, big=False):
    return random_set(kind, domain, seed, count, "h", accept, big, offset=10**6 + (7 if big else 17))
