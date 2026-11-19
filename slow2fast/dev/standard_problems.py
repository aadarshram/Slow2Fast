"""Generators for the standard generalized-planning domains: Gripper, Ferry, Miconic, Spanner, Delivery,
Logistics (the only domain-specific code for them). Each returns a problem parsed back from PDDL text.

No per-domain curriculum: training problems are random draws ordered from smallest to largest, a generic
schedule. Names are fresh random letters per problem. Every problem has at least one unsatisfied goal.
"""

import random

from slow2fast import gripper_problems as GP
from slow2fast.benchmark_problems import Names
from slow2fast.pddl import problem_from_atoms


def _finish(domain, name, types, init, goal):
    return problem_from_atoms(domain, name, types, init, goal)


def _nontrivial(init, goal):
    return not set(goal) <= set(init)


def make_ferry(domain, name, rng, locs, cars, prefix="t"):
    for _ in range(40):
        n = Names(rng, prefix)
        L, C = n.many("l", locs), n.many("c", cars)
        start = {c: rng.choice(L) for c in C}
        dest = {c: rng.choice(L) for c in C}
        init = {("at-ferry", (rng.choice(L),)), ("empty-ferry", ())} | {("at", (c, start[c])) for c in C}
        goal = {("at", (c, dest[c])) for c in C}
        if _nontrivial(init, goal):
            types = {**{l: "location" for l in L}, **{c: "car" for c in C}}
            return _finish(domain, name, types, init, goal)
    raise RuntimeError("ferry")


def make_miconic(domain, name, rng, floors, passengers, prefix="t"):
    n = Names(rng, prefix)
    F, P = n.many("f", floors), n.many("p", passengers)
    init = {("lift-at", (rng.choice(F),))}
    init |= {("above", (F[i], F[j])) for i in range(floors) for j in range(i + 1, floors)}
    goal = set()
    for p in P:
        o, d = rng.sample(F, 2)
        init.add(("origin", (p, o)))
        init.add(("destin", (p, d)))
        goal.add(("served", (p,)))
    types = {**{f: "floor" for f in F}, **{p: "passenger" for p in P}}
    return _finish(domain, name, types, init, goal)


def make_spanner(domain, name, rng, inner, nuts, extra_spanners, prefix="t"):
    n = Names(rng, prefix)
    L = n.many("l", inner + 2)  # shed, inner..., gate
    man, nut, sp = n.new("m"), n.many("n", nuts), n.many("s", nuts + extra_spanners)
    init = {("at", (man, L[0]))} | {("link", (L[i], L[i + 1])) for i in range(len(L) - 1)}
    init |= {("at", (s, rng.choice(L))) for s in sp} | {("useable", (s,)) for s in sp}
    init |= {("at", (x, L[-1])) for x in nut} | {("loose", (x,)) for x in nut}
    goal = {("tightened", (x,)) for x in nut}
    types = {**{l: "location" for l in L}, man: "man", **{x: "nut" for x in nut}, **{s: "spanner" for s in sp}}
    return _finish(domain, name, types, init, goal)


def make_delivery(domain, name, rng, width, height, packages, prefix="t"):
    for _ in range(40):
        n = Names(rng, prefix)
        cells = [(x, y) for x in range(width) for y in range(height)]
        name_of = dict(zip(cells, n.many("c", len(cells))))
        P = n.many("p", packages)
        init = {("at-robot", (name_of[rng.choice(cells)],)), ("hand-free", ())}
        for (x, y) in cells:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (x + dx, y + dy) in name_of:
                    init.add(("adjacent", (name_of[(x, y)], name_of[(x + dx, y + dy)])))
        goal = set()
        for p in P:
            s, d = rng.sample(cells, 2)
            init.add(("pkg-at", (p, name_of[s])))
            goal.add(("pkg-at", (p, name_of[d])))
        types = {**{c: "cell" for c in name_of.values()}, **{p: "package" for p in P}}
        return _finish(domain, name, types, init, goal)


def make_logistics(domain, name, rng, cities, locs, packages, airplanes=1, prefix="t"):
    n = Names(rng, prefix)
    city, types, init, places = n.many("y", cities), {}, set(), []
    airports = []
    for c in city:
        types[c] = "city"
        ap = n.new("a")
        types[ap] = "airport"
        airports.append(ap)
        here = [ap] + n.many("l", locs - 1)
        for l in here[1:]:
            types[l] = "location"
        init |= {("in-city", (l, c)) for l in here}
        places += here
        truck = n.new("t")
        types[truck] = "truck"
        init.add(("at", (truck, rng.choice(here))))
    for _ in range(airplanes):
        plane = n.new("e")
        types[plane] = "airplane"
        init.add(("at", (plane, rng.choice(airports))))
    goal, P = set(), n.many("k", packages)
    for p in P:
        types[p] = "package"
        s, d = rng.sample(places, 2)
        init.add(("at", (p, s)))
        goal.add(("at", (p, d)))
    return _finish(domain, name, types, init, goal)


def make_gripper(domain, name, rng, rooms, balls, prefix="t"):
    for _ in range(40):
        problem = GP.make(domain, name, rng, rooms, balls, 2, prefix)
        if _nontrivial(problem.initial, problem.goal):
            return problem
    raise RuntimeError("gripper")


# kind -> (maker, kwargs sampler returning (kwargs, size))
def _s(rng, lo, hi):
    return rng.randint(lo, hi)


SPECS = {
    "gripper": (make_gripper, lambda r: (lambda a, b: (dict(rooms=a, balls=b), a + b))(_s(r, 2, 4), _s(r, 1, 5))),
    "ferry": (make_ferry, lambda r: (lambda a, b: (dict(locs=a, cars=b), a + b))(_s(r, 2, 5), _s(r, 1, 5))),
    "miconic": (make_miconic, lambda r: (lambda a, b: (dict(floors=a, passengers=b), a + b))(_s(r, 2, 6), _s(r, 1, 5))),
    "spanner": (make_spanner, lambda r: (lambda a, b, c: (dict(inner=a, nuts=b, extra_spanners=c), a + b + c))(_s(r, 1, 4), _s(r, 1, 4), _s(r, 0, 2))),
    "delivery": (make_delivery, lambda r: (lambda w, h, k: (dict(width=w, height=h, packages=k), w * h + k))(_s(r, 2, 3), _s(r, 2, 3), _s(r, 1, 2))),
    "logistics": (make_logistics, lambda r: (lambda c, l, k: (dict(cities=c, locs=l, packages=k), c * l + k))(_s(r, 1, 3), _s(r, 2, 3), _s(r, 1, 4))),
}


def _draw(kind, domain, rng, count, prefix, accept, stats):
    """`count` problems that `accept` (None: all). stats["rejected"] counts those it turned away."""
    maker, sampler = SPECS[kind]
    out = []
    while len(out) < count:
        kwargs, size = sampler(rng)
        problem = maker(domain, f"{prefix}{len(out)}", rng, prefix=prefix, **kwargs)
        if accept is None or accept(problem):
            out.append((size, problem))
        else:
            stats["rejected"] = stats.get("rejected", 0) + 1
    return out


def train_set(kind, domain, seed, count, accept=None, stats=None):
    """Random problems ordered smallest to largest (a generic, domain-independent schedule)."""
    drawn = _draw(kind, domain, random.Random(seed), count, "t", accept, {} if stats is None else stats)
    return [p for _size, p in sorted(drawn, key=lambda sp: sp[0])]


def holdout_set(kind, domain, seed, count, accept=None, stats=None):
    drawn = _draw(kind, domain, random.Random(seed + 10**6 + 17), count, "h", accept, {} if stats is None else stats)
    return [p for _size, p in drawn]
