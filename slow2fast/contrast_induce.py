"""Domain-independent cue learner: contrast-driven specialization, bounded merge generalization.

Nothing here knows about blocks. The learner is given
  operators : {name: {"arity", "pre", "add", "delete"}}  (the domain model, as in slow2fast/domain.py)
  apply_fn  : (state, action) -> state                    (domain dynamics, used to find achieved goal atoms)
and only ever sees System 2 lessons: (state, goal, action, plan, optimal).
`optimal` is optional: a callable action -> bool that System 2 offers for deciding whether a competing
proposal was equally acceptable (a BFS System 2 can answer by one more search, paid only on demand).
Without it, System 2's chosen action is the only acceptable one and every other proposal in a clash is
labelled wrong.

Update principle (error-type asymmetric, local to a rule's own small exemplar memory):
  commission error (rule proposed an action System 2 judged worse)  -> specialize THAT rule with a
      literal that is true on all its stored positives and false on its stored negatives;
  omission error (nothing proposed System 2's action)               -> generalize the nearest rule of
      that action by dropping only the literals the new case violates, vetoed by its own negatives;
  silence never causes specialization; known wrong cases are never generalized over.

Rules match by recognition: one *distinct* action must be proposed, otherwise System 2 answers. Three
deliberate refinements of "distinct":
  symmetry   proposals that differ only by swapping interchangeable objects (state and goal unchanged by
             the swap, e.g. two free grippers) are one choice, not a conflict. Domain-independent check.
  ties       (opt-in, needs a judge) two rules that practice has shown to propose equally acceptable
             actions together are not in conflict; any wrong proposal makes them forget each other.
  full_cover a rule is forked into more specific rules only if the children keep ALL its stored
             positives; otherwise the rule is kept and yields (exception link) to the rule that is right.
"""

# A literal is (sign, src, pred, args): sign "+"/"-", src "s" state, "g" goal, "d" derived.
# Derived (optional): sat:p(args) / unsat:p(args) for every goal atom, comparing state to goal.

_SRC_RANK = {"d": 0, "g": 1, "s": 2}

import functools


def _complexity(lit):
    """Cost of a candidate condition: 1, plus 1 per fresh existential object it introduces, plus 1 if negated."""
    sign, _src, _pred, args = lit
    fresh = len({v for v in args if v.startswith("?n") or v.startswith("?v")})
    return 1 + fresh + (1 if sign == "-" else 0)


def symmetric(state, goal, a, b):
    """True when swapping interchangeable objects maps action a to action b and leaves both the state and
    the goal unchanged (type atoms are part of the state, so only same-type objects can be swapped). Such
    actions are the same choice, not competing ones: e.g. picking with the left or the right free gripper."""
    if a[0] != b[0] or len(a[1]) != len(b[1]):
        return False
    perm = {}
    for x, y in zip(a[1], b[1]):
        if x != y:
            if perm.get(x, y) != y or perm.get(y, x) != x:
                return False
            perm[x], perm[y] = y, x
    if not perm:
        return True

    def image(atoms):
        return frozenset((p, tuple(perm.get(o, o) for o in args)) for p, args in atoms)

    return image(state) == frozenset(state) and image(goal) == frozenset(goal)


class _Acceptable:
    """Membership test for "was this action acceptable here": System 2's own action, or whatever the
    optional judge says (asked lazily, at most once per action)."""

    def __init__(self, action, judge, same=None):
        self.action, self.judge, self.same, self._memo = action, judge, same, {}

    def __contains__(self, act):
        if act == self.action:
            return True
        if self.same is not None and self.same(act, self.action):
            return True
        if self.judge is None:
            return False
        if act not in self._memo:
            self._memo[act] = bool(self.judge(act))
        return self._memo[act]


def ground_ops(operators, action):
    name, args = action
    spec = operators[name]
    binding = {f"?{i}": args[i] for i in range(spec["arity"])}

    def ground(literals):
        return {(p, tuple(binding[s] for s in slots)) for p, slots in literals}

    return ground(spec["pre"]), ground(spec["add"]), ground(spec["delete"])


def lifted_pre(operators, name, params):
    spec = operators[name]
    binding = {f"?{i}": params[i] for i in range(spec["arity"])}
    return [("+", "s", p, tuple(binding[s] for s in slots)) for p, slots in spec["pre"]]


def make_view(state, goal, derived):
    view = {("s", p, a) for p, a in state} | {("g", p, a) for p, a in goal}
    if derived:
        state = set(state)
        for p, a in goal:
            view.add(("d", ("sat:" if (p, a) in state else "unsat:") + p, a))
    return frozenset(view)


@functools.lru_cache(maxsize=1024)
def _objects(view):
    return tuple(sorted({o for _s, _p, args in view for o in args}))


def _holds(lit, binding, view):
    sign, src, pred, args = lit
    present = (src, pred, tuple(binding[v] for v in args)) in view
    return present if sign == "+" else not present


def _var_order(params, lits):
    order = list(params)
    for sign, _src, _pred, args in lits:
        if sign == "+":
            for v in args:
                if v not in order:
                    order.append(v)
    return order


def _safe(params, lits):
    order = set(_var_order(params, lits))
    return all(v in order for _sign, _src, _pred, args in lits for v in args)


@functools.lru_cache(maxsize=None)
def _compile(params, lits):
    """Join plan for a rule body: variable order and, per variable, the literals that become checkable
    once it is bound. Depends only on the rule, so it is computed once."""
    if not _safe(params, lits):
        return None
    order = _var_order(params, lits)
    index = {v: i for i, v in enumerate(order)}
    checks = [[] for _ in order]
    zero = []
    for lit in lits:
        if not lit[3]:
            zero.append(lit)
        else:
            checks[max(index[v] for v in lit[3])].append(lit)
    return tuple(order), tuple(tuple(c) for c in checks), tuple(zero)


def iter_bindings(params, lits, view, fixed=None):
    """Injective bindings of all rule variables satisfying every literal."""
    plan = _compile(tuple(params), tuple(lits))
    if plan is None:
        return
    order, checks, zero = plan
    if not all(_holds(lit, {}, view) for lit in zero):
        return
    objects = _objects(view)
    fixed = fixed or {}
    binding = {}
    used = set()

    def rec(i):
        if i == len(order):
            yield dict(binding)
            return
        var = order[i]
        options = (fixed[var],) if var in fixed else objects
        for obj in options:
            if obj in used:
                continue
            binding[var] = obj
            if all(_holds(lit, binding, view) for lit in checks[i]):
                used.add(obj)
                yield from rec(i + 1)
                used.discard(obj)
            del binding[var]

    yield from rec(0)


@functools.lru_cache(maxsize=60_000)
def _groundings(op, params, lits, view):
    found = []
    for b in iter_bindings(params, lits, view):
        act = (op, tuple(b[p] for p in params))
        if act not in found:
            found.append(act)
    return tuple(found)


class Rule:
    def __init__(self, op, params, lits, protected):
        self.op = op
        self.params = tuple(params)
        self.lits = list(lits)
        self.protected = frozenset(protected)
        self.confirmations = 0
        self.rid = None
        self.defer = set()  # ids of rules this one yields to (exception link: this AND NOT that)
        self.pos = []  # (view, action) cases this rule was right on
        self.neg = []  # (view, action) cases where it proposed an action judged worse
        self.pinned = {}  # condition -> the (few) bad cases it was added to exclude, kept while it exists
        self._min_key = None  # what the last minimisation pass looked at; skip if nothing changed
        self.last_used = 0  # lesson number when it last agreed, merged or fired successfully

    def groundings(self, view, lits=None):
        lits = self.lits if lits is None else lits
        return list(_groundings(self.op, self.params, tuple(lits), view))

    def signature(self):
        return (self.op, self.params, tuple(self.lits))


class ContrastLibrary:
    accepts_optimal = True

    def __init__(
        self,
        operators,
        apply_fn,
        threshold=2,
        spec_threshold=2,
        derived=False,
        allow_neg=True,
        merge=True,
        defer=True,
        symmetry=True,
        ties=False,
        full_cover=True,
        outcomes=False,
        order=False,
        minimize=False,
        prune=False,
        audit_rate=0.0,
        prune_age=30,
        bundle=False,
        memory=6,
        max_new=2,
    ):
        if bundle:  # every learning-time mechanism on; none of them adds work when System 1 decides
            outcomes = order = minimize = prune = True
            audit_rate = audit_rate or 0.25
        self.operators = operators
        self.apply_fn = apply_fn
        self.threshold = threshold
        self.spec_threshold = spec_threshold
        self.derived = derived
        self.allow_neg = allow_neg
        self.merge = merge
        self.defer = defer
        self.symmetry = symmetry
        self.prune_flag = prune  # merge identical rules and forget stale unpracticed ones
        self.prune_age = prune_age
        self.audit_rate = audit_rate  # share of System 1 proposals spot-checked against System 2 while learning
        self._audit_n = 0
        self.lesson = 0
        self.order = order  # try cheaper discriminating conditions first (see _complexity)
        self.minimize = minimize  # drop conditions no stored bad case needs, once a rule is practiced
        self.learns_outcomes = outcomes  # also learn from the outcomes of System 1's own actions (see record_outcome)
        self._descendants = {}  # rule id -> ids of the rules it was forked into
        self.full_cover = full_cover  # fork a rule only if the children keep ALL its positives; else defer
        self.ties = ties  # tolerate proposals that practice has shown to be equally acceptable
        self.peers = {}
        self._next_id = 0
        self.memory = memory
        self.max_new = max_new
        self.rules = []
        self._fresh = 0
        self._cover_memo = {}
        self.stats = {"merge": 0, "new": 0, "specialize": 0, "fork": 0, "spec_failed": 0, "defer": 0, "bad_labels": 0, "outcome_neg": 0, "minimized": 0, "pruned": 0, "audits": 0, "audit_wrong": 0}

    # ---- recognition -------------------------------------------------------------------------
    def _register(self, rule):
        rule.rid = self._next_id
        rule.last_used = self.lesson
        self._next_id += 1
        return rule

    def _ground_all(self, view):
        """[(index, rule, groundings)] after exception links: a rule yields while a practiced rule it
        defers to is itself recognising something here."""
        raw = [(i, r, r.groundings(view)) for i, r in enumerate(self.rules)]
        active = {r.rid for _i, r, g in raw if g and r.confirmations >= self.threshold}
        return [(i, r, [] if (r.defer & active) else g) for i, r, g in raw]

    def _view(self, state, goal):
        return make_view(state, goal, self.derived)

    def propose(self, state, goal):
        view = self._view(state, goal)
        votes = {}
        for i, rule, grounded in self._ground_all(view):
            if rule.confirmations < self.threshold:
                continue
            for act in grounded:
                votes.setdefault(act, []).append(i)
        if len(votes) > 1 and self.symmetry:
            state, goal = frozenset(state), frozenset(goal)
            first = next(iter(votes))
            if all(symmetric(state, goal, first, other) for other in votes):
                votes = {min(votes): votes[min(votes)]}
        if len(votes) > 1 and self.ties and self._all_peers(votes):
            best = max(votes, key=lambda a: (max(self.rules[i].confirmations for i in votes[a]), tuple(-ord(c) for c in str(a))))
            votes = {best: votes[best]}
        if len(votes) != 1:
            return None
        act, idxs = next(iter(votes.items()))
        best = max(idxs, key=lambda i: self.rules[i].confirmations)
        return f"r{best}", act

    def _all_peers(self, votes):
        """True when every pair of rules behind the competing proposals has been seen to propose
        equally acceptable actions together (a rule that proposes several counts with itself)."""
        owners = {}
        for act, idxs in votes.items():
            for i in idxs:
                owners.setdefault(self.rules[i].rid, set()).add(act)
        rids = sorted(owners)
        for x, a in enumerate(rids):
            if len(owners[a]) > 1 and self.peers.get((a, a), 0) < self.threshold:
                return False
            for b in rids[x + 1 :]:
                if owners[a] == owners[b] == {next(iter(owners[a]))} and len(owners[a]) == 1:
                    continue  # they agree on the same single action
                if self.peers.get((a, b), 0) < self.threshold:
                    return False
        return True

    def _note_peers(self, hits, acceptable, bad):
        """After a lesson: rules that proposed distinct acceptable actions together become (more) peers;
        a rule that proposed something wrong forgets its peers."""
        for i in bad:
            rid = self.rules[i].rid
            for key in [k for k in self.peers if rid in k]:
                del self.peers[key]
        good = {i: [a for a in g if a in acceptable] for i, g in hits.items() if i not in bad}
        owners = sorted(good)
        for x, i in enumerate(owners):
            if len(set(good[i])) > 1:
                key = (self.rules[i].rid,) * 2
                self.peers[key] = self.peers.get(key, 0) + 1
            for j in owners[x + 1 :]:
                if set(good[i]) != set(good[j]) or len(set(good[i])) > 1:
                    if good[i] and good[j] and set(good[i]) | set(good[j]) != set(good[i]) & set(good[j]):
                        key = tuple(sorted((self.rules[i].rid, self.rules[j].rid)))
                        self.peers[key] = self.peers.get(key, 0) + 1

    def diagnose(self, state, goal):
        view = self._view(state, goal)
        practiced, unpracticed = {}, {}
        for i, rule, grounded in self._ground_all(view):
            for act in grounded:
                (practiced if rule.confirmations >= self.threshold else unpracticed).setdefault(act, []).append(i)
        if len(practiced) == 1:
            return "unique", list(practiced)
        if len(practiced) > 1:
            return "multi_match", list(practiced)
        if unpracticed:
            return "below_threshold", list(unpracticed)
        return "no_match", []

    def counts(self):
        return {f"r{i}": r.confirmations for i, r in enumerate(self.rules)}

    def note_success(self, name):
        rule = self.rules[int(name[1:])]
        rule.confirmations += 1
        rule.last_used = self.lesson

    # ---- learning from the outcome of System 1's own action ------------------------------------
    def voters(self, state, goal, action):
        """Ids of the practiced rules that proposed `action` here (who to blame if it turns out badly)."""
        view = self._view(frozenset(state), frozenset(goal))
        return [r.rid for _i, r, g in self._ground_all(view) if r.confirmations >= self.threshold and action in g]

    def _alive(self, rids):
        """The rules in the library today that descend from the given ids (rules get forked and replaced)."""
        out, stack = set(), list(rids)
        while stack:
            rid = stack.pop()
            out.add(rid)
            stack.extend(self._descendants.get(rid, []))
        return out

    def record_outcome(self, state, goal, action, voter_rids, kind):
        """System 1 proposed `action` here and it turned out badly. kind: "dead_end" (the next state is
        unsolvable) or "wrong" (a learning-time spot-check found a better action): strong evidence, acted on at
        once; or "loop" (it would revisit a state): weaker, needs the usual number of negatives. The situation becomes a negative example of every rule that proposed it,
        and those rules are specialised exactly as for a wrong proposal."""
        state, goal = frozenset(state), frozenset(goal)
        view = self._view(state, goal)
        ids = self._alive(voter_rids)
        for rule in [r for r in self.rules if r.rid in ids and action in r.groundings(view)]:
            self._remember(rule.neg, (view, action))
            self.stats["outcome_neg"] += 1
            self._specialize(rule, (), min_neg=1 if kind in ("dead_end", "wrong") else None)

    def audit_due(self):
        """True on every k-th System 1 proposal while learning (k = 1 / audit_rate)."""
        if self.audit_rate <= 0:
            return False
        self._audit_n += 1
        return self._audit_n % max(1, round(1 / self.audit_rate)) == 0

    def audit_ok(self, state, goal, action, first, judge):
        """Is System 1's `action` acceptable given System 2's first action `first` (and its optional judge)?"""
        state, goal = frozenset(state), frozenset(goal)
        same = (lambda x, y: symmetric(state, goal, x, y)) if self.symmetry else None
        ok = action in _Acceptable(first, judge, same)
        self.stats["audits"] += 1
        self.stats["audit_wrong"] += int(not ok)
        return ok

    # ---- learning from one System 2 lesson ---------------------------------------------------
    def observe(self, state, goal, action, plan=None, optimal=None):
        self.lesson += 1
        state, goal = frozenset(state), frozenset(goal)
        view = self._view(state, goal)
        same = (lambda x, y: symmetric(state, goal, x, y)) if self.symmetry else None
        acceptable = _Acceptable(action, optimal, same)
        hits = {i: g for i, _rule, g in self._ground_all(view) if g}
        agreeing = {}
        bad = {}
        for i, g in hits.items():
            good = [a for a in g if a in acceptable]
            if good:
                agreeing[i] = action if action in good else good[0]
            wrong = [a for a in g if a not in acceptable]
            if wrong:
                bad[i] = wrong
        for i, act in agreeing.items():
            rule = self.rules[i]
            self._remember(rule.pos, (view, act))
            rule.last_used = self.lesson
            if i not in bad:
                rule.confirmations += 1
            self._minimize(rule)
        for i, acts in bad.items():
            for act in acts:
                self._remember(self.rules[i].neg, (view, act))
            self.stats["bad_labels"] += len(acts)
        if self.ties:
            self._note_peers(hits, acceptable, bad)
        touched = [self.rules[i] for i in sorted(bad)]
        if not agreeing:
            touched += [r for r in self._learn_omission(state, goal, view, action, plan, acceptable) if r not in touched]
        partners = [self.rules[i] for i in agreeing]
        for rule in touched:
            self._specialize(rule, partners)
        self._prune()

    def _remember(self, store, item):
        if item not in store:
            store.append(item)
            del store[: -self.memory]

    # ---- omission: generalize nearest rule, else seed a new one ------------------------------
    def _learn_omission(self, state, goal, view, action, plan, acceptable):
        if self.merge:
            best = None
            for i, rule in enumerate(self.rules):
                if rule.op != action[0]:
                    continue
                merged = self._merged_lits(rule, view, action)
                if merged is None:
                    continue
                if not self._merge_safe(rule, merged, view, acceptable):
                    continue
                dropped = len(rule.lits) - len(merged)
                key = (dropped, -rule.confirmations)
                if best is None or key < best[0]:
                    best = (key, i, merged)
            if best is not None:
                _key, i, merged = best
                rule = self.rules[i]
                rule.lits = merged
                rule.last_used = self.lesson
                rule.pinned = {l: c for l, c in rule.pinned.items() if l in merged}
                self._remember(rule.pos, (view, action))
                rule.confirmations += 1
                self.stats["merge"] += 1
                return [rule]
        rule = self._seed(state, goal, view, action, plan)
        if rule is None:
            return []
        self.rules.append(self._register(rule))
        self.stats["new"] += 1
        for act in rule.groundings(view):
            if act not in acceptable:
                self._remember(rule.neg, (view, act))
        return [rule]

    def _merged_lits(self, rule, view, action):
        """Keep the literals of `rule` that hold on the new case under the best variable mapping."""
        extras = [v for v in _var_order(rule.params, rule.lits) if v not in rule.params]
        objects = _objects(view)
        free = [o for o in objects if o not in action[1]]
        if len(extras) > len(free) or len(free) ** len(extras) > 20000:
            return None
        fixed = dict(zip(rule.params, action[1]))
        best = None

        def assign(i, binding, used):
            nonlocal best
            if i == len(extras):
                sat = [lit for lit in rule.lits if _holds(lit, binding, view)]
                if best is None or len(sat) > len(best):
                    best = sat
                return
            for obj in free:
                if obj not in used:
                    binding[extras[i]] = obj
                    assign(i + 1, binding, used | {obj})
                    del binding[extras[i]]

        assign(0, dict(fixed), set())
        if best is None:
            return None
        order = set(_var_order(rule.params, [l for l in best if l[0] == "+"]))
        merged = [l for l in best if l[0] == "+" or all(v in order for v in l[3])]
        if not set(rule.protected) <= set(merged):
            return None
        if len(merged) == len(rule.lits):
            return None
        return merged

    def _merge_safe(self, rule, merged, view, acceptable):
        for nview, nact in self._neg_all(rule):
            if nact in rule.groundings(nview, merged):
                return False
        for act in rule.groundings(view, merged):
            if act not in acceptable:
                return False
        return True

    def _seed(self, state, goal, view, action, plan):
        name, args = action
        if name not in self.operators:
            return None
        params = tuple(f"?a{i}" for i in range(len(args)))
        pre = lifted_pre(self.operators, name, params)
        lits = list(pre)
        atom = self._permanent_goal_atom(state, goal, plan or [action], action)
        if atom is not None:
            pred, aargs = atom
            names = dict(zip(args, params))
            mapped = []
            for o in aargs:
                if o not in names:
                    names[o] = f"?g{len(names)}"
                mapped.append(names[o])
            lit = ("+", "g", pred, tuple(mapped))
            if lit not in lits:
                lits.append(lit)
        rule = Rule(name, params, lits, pre)
        rule.confirmations = 1
        self._remember(rule.pos, (view, action))
        if action not in rule.groundings(view):
            return None
        return rule

    def _permanent_goal_atom(self, state, goal, plan, action):
        """A goal atom that becomes true during the plan and stays true; prefer one the action adds."""
        current = frozenset(state)
        first, after = {}, []
        for index, step in enumerate(plan):
            try:
                current = self.apply_fn(current, step)
            except ValueError:
                return None
            after.append(current)
            for atom in goal:
                if atom in current and atom not in first:
                    first[atom] = index
        cands = [
            (index, atom)
            for atom, index in first.items()
            if atom not in state and all(atom in s for s in after[index:])
        ]
        if not cands:
            return None
        added = ground_ops(self.operators, action)[1]
        preferred = [c for c in cands if c[1] in added]
        touching = [c for c in cands if set(c[1][1]) & set(action[1])]
        return sorted(preferred or touching or cands)[0][1]

    # ---- commission: contrast-driven specialization (with covering when one cue cannot fit) ---
    def _specialize(self, rule, partners=(), min_neg=None):
        need = self.spec_threshold if min_neg is None else min_neg
        if len(rule.neg) < need or rule not in self.rules:
            return
        firing = [(v, a) for v, a in rule.neg if a in rule.groundings(v)]
        if not firing:
            return
        groups, remaining = [], list(rule.pos)
        while remaining and len(groups) < 4:
            found = self._best_cover(rule, remaining, firing)
            if found is None:
                break
            cand, covered = found
            groups.append((cand, covered))
            remaining = [p for p in remaining if p not in covered]
        if self.full_cover and remaining:
            groups = []  # a partial cover would silently drop positives: keep the rule, defer instead
        if not groups:
            self.stats["spec_failed"] += 1
            if self.defer:
                for other in partners:
                    if other is not rule and rule.rid not in other.defer and other.rid not in rule.defer:
                        rule.defer.add(other.rid)
                        self.stats["defer"] += 1
            return
        children = []
        for cand, covered in groups:
            added = [self._rename(l) for l in cand]
            child = Rule(rule.op, rule.params, rule.lits + added, rule.protected)
            self._register(child)
            child.defer = set(rule.defer)
            child.pos = list(covered)
            child.last_used = self.lesson
            child.neg = list(rule.neg)
            child.pinned = {l: list(c) for l, c in rule.pinned.items()}
            for lit in added:
                child.pinned[lit] = list(firing[-3:])
            child.confirmations = min(rule.confirmations, len(covered)) if len(groups) > 1 else rule.confirmations
            children.append(child)
        at = self.rules.index(rule)
        self._descendants[rule.rid] = [c.rid for c in children]
        self.rules[at : at + 1] = children
        for key in [k for k in self.peers if rule.rid in k]:
            for child in children:
                new = tuple(sorted(child.rid if r == rule.rid else r for r in key))
                self.peers[new] = max(self.peers.get(new, 0), self.peers[key])
        for other in self.rules:
            if rule.rid in other.defer:
                other.defer.discard(rule.rid)
                other.defer |= {c.rid for c in children}
        self.stats["specialize" if len(children) == 1 else "fork"] = self.stats.get(
            "specialize" if len(children) == 1 else "fork", 0
        ) + 1
        for child in children:
            self._minimize(child)

    def _remove(self, rule, replace_with=None):
        """Take a rule out of the library, keeping the links other rules hold to it consistent."""
        self.rules.remove(rule)
        self.stats["pruned"] += 1
        for other in self.rules:
            if rule.rid in other.defer:
                other.defer.discard(rule.rid)
                if replace_with is not None and replace_with.rid != other.rid:
                    other.defer.add(replace_with.rid)
        for key in [k for k in self.peers if rule.rid in k]:
            del self.peers[key]
        if replace_with is not None:
            self._descendants[rule.rid] = [replace_with.rid]

    def _prune(self):
        """Merge rules that have become identical, and forget unpracticed rules nothing has used for a while."""
        if not self.prune_flag:
            return
        first = {}
        for rule in list(self.rules):
            key = (rule.op, rule.params, frozenset(rule.lits))
            keep = first.setdefault(key, rule)
            if keep is rule:
                continue
            keep.confirmations += rule.confirmations
            for case in rule.pos:
                self._remember(keep.pos, case)
            for case in rule.neg:
                self._remember(keep.neg, case)
            for lit, cases in rule.pinned.items():
                keep.pinned.setdefault(lit, list(cases))
            keep.defer |= rule.defer - {keep.rid, rule.rid}
            keep.last_used = max(keep.last_used, rule.last_used)
            self._remove(rule, replace_with=keep)
        for rule in list(self.rules):
            if rule.confirmations < self.threshold and self.lesson - rule.last_used > self.prune_age:
                self._remove(rule)

    def _neg_all(self, rule):
        """The bad cases the rule must still exclude: the bounded store plus those pinned to its conditions."""
        out = list(rule.neg)
        for cases in rule.pinned.values():
            for case in cases:
                if case not in out:
                    out.append(case)
        return out

    def _minimize(self, rule):
        """Drop conditions that no remembered bad case needs, most complex first. Dropping a condition can only
        make the rule match more, so its good cases stay covered; only bad cases need checking."""
        if not self.minimize or rule.confirmations < self.threshold:
            return
        negs = self._neg_all(rule)
        key = (tuple(rule.lits), tuple(negs))
        if rule._min_key == key:
            return
        for lit in sorted((l for l in rule.lits if l not in rule.protected), key=_complexity, reverse=True):
            trial = [l for l in rule.lits if l != lit]
            if not _safe(rule.params, trial):
                continue
            if all(act not in rule.groundings(view, trial) for view, act in negs):
                rule.lits = trial
                rule.pinned.pop(lit, None)
                self.stats["minimized"] += 1
        rule._min_key = (tuple(rule.lits), tuple(self._neg_all(rule)))

    def _rename(self, lit):
        sign, src, pred, args = lit
        out = []
        for v in args:
            if v.startswith("?n"):
                v = f"?v{self._fresh}_{v[2:]}"
            out.append(v)
        return (sign, src, pred, tuple(out))

    def _best_cover(self, rule, positives, firing):
        """Smallest refinement that excludes every stored negative and keeps the most positives.

        Tries each remaining positive as the seed, latest first, so one hard case cannot block a fork.
        """
        self._fresh += 1
        memo_key = (rule.op, rule.params, tuple(rule.lits), tuple(positives), tuple(self._neg_all(rule)), tuple(firing[-3:]), self.order)
        if memo_key in self._cover_memo:
            return self._cover_memo[memo_key]
        found = self._search_cover(rule, positives, firing)
        self._cover_memo[memo_key] = found
        return found

    def _search_cover(self, rule, positives, firing):
        negs = firing[-3:]
        neg_pool = []
        if self.allow_neg:
            for neg in negs:
                neg_pool += self._neg_pool(rule, neg)

        def key(lit):
            if self.order:
                return (_complexity(lit), _SRC_RANK[lit[1]], lit[2], lit[3])
            new = sum(1 for v in lit[3] if v.startswith("?n"))
            return (new, _SRC_RANK[lit[1]], 0 if lit[0] == "+" else 1, lit[2], lit[3])

        all_negs = self._neg_all(rule)

        def evaluate(extra, seed):
            lits = rule.lits + list(extra)
            if not _safe(rule.params, lits):
                return None
            for view, act in all_negs:
                if act in rule.groundings(view, lits):
                    return None
            covered = [p for p in positives if p[1] in rule.groundings(p[0], lits)]
            return covered if seed in covered else None

        for seed in reversed(positives):
            pos_pool = sorted(set(self._pos_pool(rule, seed)), key=key)
            plain = [l for l in pos_pool if not any(v.startswith("?n") for v in l[3])]
            joined = [l for l in pos_pool if any(v.startswith("?n") for v in l[3])]
            neg_plain = sorted({l for l in neg_pool if not any(v.startswith("?n") for v in l[3])}, key=key)
            neg_joined = sorted({l for l in neg_pool if any(v.startswith("?n") for v in l[3])}, key=key)
            best = None
            for lit in plain + joined + neg_plain:
                covered = evaluate([lit], seed)
                if covered is None:
                    continue
                if len(covered) == len(positives):
                    return [lit], covered
                if best is None or len(covered) > len(best[1]):
                    best = ([lit], covered)
            if self.max_new >= 2:
                first = plain[:25] + joined[:40] + neg_plain[:15]
                second = plain[:25] + joined[:40] + neg_plain[:15] + neg_joined[:25]
                for i, a in enumerate(first):
                    for b in second:
                        if b == a or (b in first and first.index(b) <= i):
                            continue
                        covered = evaluate([a, b], seed)
                        if covered is None:
                            continue
                        if best is None or len(covered) > len(best[1]):
                            best = ([a, b], covered)
                            if len(covered) == len(positives):
                                return best
            if best is not None:
                return best
        return None

    def _lift(self, atom_args, image_inv, names):
        """Variables for an atom's objects: bound ones through the rule's binding, the rest through the
        per-object names of this binding (so literals lifted from the same case can join on them)."""
        out, extra = [], set()
        for o in atom_args:
            if o in image_inv:
                out.append(image_inv[o])
            else:
                extra.add(o)
                out.append(names[o])
        return tuple(out), extra

    @staticmethod
    def _extra_names(view, image_inv):
        return {o: f"?n{i}" for i, o in enumerate(o for o in _objects(view) if o not in image_inv)}

    def _pos_pool(self, rule, case):
        """Atoms true on a positive case, lifted through the rule's own bindings. A literal may introduce up
        to two fresh objects (e.g. carry(?n0,?n1)); one that touches no bound object must introduce two."""
        view, act = case
        pool = []
        fixed = dict(zip(rule.params, act[1]))
        for th in list(iter_bindings(rule.params, rule.lits, view, fixed))[:20]:
            inv = {o: v for v, o in th.items()}
            names = self._extra_names(view, inv)
            for src, pred, args in view:
                lifted, extra = self._lift(args, inv, names)
                if len(extra) > 2 or (args and len(extra) < 2 and not any(o in inv for o in args)):
                    continue
                lit = ("+", src, pred, lifted)
                if lit not in rule.lits:
                    pool.append(lit)
        return pool

    def _neg_pool(self, rule, firing_neg):
        """Negated atoms true on the failing case, with the same fresh-object convention."""
        view, act = firing_neg
        pool = []
        fixed = dict(zip(rule.params, act[1]))
        for th in list(iter_bindings(rule.params, rule.lits, view, fixed))[:20]:
            inv = {o: v for v, o in th.items()}
            names = self._extra_names(view, inv)
            for src, pred, args in view:
                lifted, extra = self._lift(args, inv, names)
                if len(extra) > 2 or (args and len(extra) < 2 and not any(o in inv for o in args)):
                    continue
                lit = ("-", src, pred, lifted)
                if lit not in rule.lits:
                    pool.append(lit)
        return pool
