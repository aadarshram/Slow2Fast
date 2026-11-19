"""PDDL front end. Domains and problems come from .pddl files, parsed by the pyperplan library.

What this module provides (nothing in it knows about any particular domain):
  PddlDomain   the lifted operator model read from a domain file, in the dict format the learners use,
               plus world semantics (apply an action, list applicable actions, goal test).
  PddlProblem  objects, initial state and goal read from a problem file (or built from atoms and parsed
               back from generated PDDL text).
  fact helpers to move between atoms ("on", ("a", "b")) and pyperplan fact strings "(on a b)".

Optional static-relation closure (PddlDomain(..., derive_static=True), off by default): for every static binary
predicate (never added or deleted by any operator) that is directed (not symmetric) and chains (some object is both
a first and a second argument), the problem also carries "closure:p" (the transitive closure, when it adds pairs) and
"closure-inv:p" (its inverse). They are computed once when the problem is read, from the problem's own facts, and
mention no particular domain: leftof/above/succ/next/link become "anywhere to the left", "higher", "ahead of".
Undirected relations (adjacent, neighbor) and state-dependent structure get nothing.

Typing is compiled into unary static predicates "type:T": every object of type T (and of its subtypes'
ancestors) carries type:T in the state, and every typed operator parameter gets a type:T precondition.
So learners and rules need no notion of types.

Supported PDDL: STRIPS with :typing (what pyperplan parses). No constants, negative preconditions,
conditional effects or numeric fluents.
"""

from pathlib import Path

from pyperplan import grounding
from pyperplan.pddl.parser import Parser

TYPE_PREFIX = "type:"
DERIVED_PREFIXES = ("closure:", "closure-inv:")
MAX_DERIVED_ATOMS = 4000  # skip a relation whose closure would be larger than this


def fact(pred, args):
    return "(" + " ".join((pred,) + tuple(args)) + ")"


def parse_fact(text):
    parts = text.strip().strip("()").split()
    return parts[0], tuple(parts[1:])


class PddlDomain:
    def __init__(self, path, derive_static=False):
        self.path = Path(path)
        self.derive_static = derive_static
        parser = Parser(str(self.path))
        self.pp = parser.parse_domain()
        if self.pp.constants:
            raise NotImplementedError("PDDL :constants are not supported")
        self.name = self.pp.name
        self.parents = {
            name: (t.parent.name if getattr(t, "parent", None) is not None else None)
            for name, t in self.pp.types.items()
        }
        self.predicates = {name: len(pred.signature) for name, pred in self.pp.predicates.items()}
        self.operators = {}
        for name, action in self.pp.actions.items():
            self.operators[name] = self._compile(action)
        changed = {p for spec in self.operators.values() for p, _slots in spec["add"] + spec["delete"]}
        self.static_relations = sorted(
            p for p, arity in self.predicates.items() if arity == 2 and p not in changed and not p.startswith(TYPE_PREFIX)
        )

    # ---- lifted operator model ---------------------------------------------------------------
    def _compile(self, action):
        slot, types = {}, []
        for var, var_types in action.signature:
            if len(var_types) != 1:
                raise NotImplementedError("either-types are not supported")
            slot[var] = f"?{len(slot)}"
            types.append(var_types[0].name)

        def lift(preds):
            return [(p.name, tuple(slot[a[0]] for a in p.signature)) for p in preds]

        pre = lift(action.precondition)
        for index, tname in enumerate(types):
            if tname != "object":
                pre.append((TYPE_PREFIX + tname, (f"?{index}",)))
        return {
            "arity": len(slot),
            "pre": tuple(pre),
            "add": tuple(lift(action.effect.addlist)),
            "delete": tuple(lift(action.effect.dellist)),
            "types": tuple(types),
        }

    def ancestors(self, tname):
        out = []
        while tname is not None and tname != "object":
            out.append(tname)
            tname = self.parents.get(tname)
        return out

    def type_atoms(self, object_types):
        atoms = set()
        for obj, tname in object_types.items():
            for t in self.ancestors(tname):
                atoms.add((TYPE_PREFIX + t, (obj,)))
        return atoms

    def derived_static_atoms(self, atoms):
        """Closure atoms for the directed, chaining static binary relations among `atoms` (see module docstring)."""
        if not self.derive_static:
            return set()
        out = set()
        for p in self.static_relations:
            edges = {(args[0], args[1]) for pred, args in atoms if pred == p}
            if not edges or not ({x for x, _ in edges} & {y for _, y in edges}):
                continue  # nothing to chain
            if all((y, x) in edges for x, y in edges):
                continue  # symmetric: no direction to derive
            successors = {}
            for x, y in edges:
                successors.setdefault(x, set()).add(y)
            closure = set()
            for x in successors:
                seen, stack = set(), list(successors[x])
                while stack:
                    y = stack.pop()
                    if y not in seen:
                        seen.add(y)
                        stack.extend(successors.get(y, ()))
                closure |= {(x, y) for y in seen}
            if len(closure) > MAX_DERIVED_ATOMS:
                continue
            if len(closure) > len(edges):
                out |= {("closure:" + p, (x, y)) for x, y in closure}
            out |= {("closure-inv:" + p, (y, x)) for x, y in closure}
        return out

    # ---- world semantics ---------------------------------------------------------------------
    def ground_ops(self, action):
        name, args = action
        spec = self.operators[name]
        if len(args) != spec["arity"]:
            raise ValueError(f"bad arity for {action}")
        binding = {f"?{i}": args[i] for i in range(spec["arity"])}

        def ground(literals):
            return {(p, tuple(binding[s] for s in slots)) for p, slots in literals}

        return ground(spec["pre"]), ground(spec["add"]), ground(spec["delete"])

    def apply(self, state, action):
        pre, add, delete = self.ground_ops(action)
        state = set(state)
        if not pre <= state:
            raise ValueError(f"{action[0]} is not applicable: {action}")
        state -= delete
        state |= add
        return frozenset(state)

    def applicable_actions(self, state, objects):
        state = set(state)
        objects = sorted(objects)
        found = []
        for name, spec in self.operators.items():
            arity = spec["arity"]
            checks = [[] for _ in range(max(arity, 1))]
            for pred, slots in spec["pre"]:
                last = max((int(s[1:]) for s in slots), default=0)
                checks[last].append((pred, slots))
            binding = []

            def rec(i):
                if i == arity:
                    found.append((name, tuple(binding)))
                    return
                for obj in objects:
                    binding.append(obj)
                    if all((p, tuple(binding[int(s[1:])] for s in slots)) in state for p, slots in checks[i]):
                        rec(i + 1)
                    binding.pop()

            if arity == 0:
                if all((p, ()) in state for p, _s in spec["pre"]):
                    found.append((name, ()))
            else:
                rec(0)
        return found

    @staticmethod
    def goal_holds(state, goal):
        return set(goal) <= set(state)


class PddlProblem:
    """A problem instance. `blocks`/`initial`/`goal` mirror the older Problem class so episode code
    can treat both alike; `initial` includes the static type atoms."""

    def __init__(self, domain, name, object_types, init, goal, pp=None):
        self.domain = domain
        self.name = name
        self.object_types = dict(object_types)
        self.objects = tuple(self.object_types)
        self.blocks = self.objects
        self.initial = frozenset(init) | frozenset(domain.type_atoms(self.object_types))
        if domain.derive_static:
            self.initial |= frozenset(domain.derived_static_atoms(init))
        self.goal = frozenset(goal)
        self._pp = pp
        self._task = None
        self._heuristics = {}

    def ground_task(self):
        """pyperplan's grounded STRIPS task (statics and goal-irrelevant operators removed)."""
        if self._task is None:
            task = grounding.ground(self._pp)
            # pyperplan builds operators from sets of strings, so their order (hence every tie-break in
            # search) would change with the process hash seed. Fix it.
            task.operators = sorted(task.operators, key=lambda op: op.name)
            self._task = task
        return self._task


def _atoms_of(predicates):
    return {(p.name, tuple(a[0] for a in p.signature)) for p in predicates}


def _from_parsed(domain, pp_problem):
    objects = {name: t.name for name, t in pp_problem.objects.items()}
    init = _atoms_of(pp_problem.initial_state)
    goal = _atoms_of(pp_problem.goal)
    return PddlProblem(domain, pp_problem.name, objects, init, goal, pp=pp_problem)


def load_problem(domain, path):
    """Read a problem from a .pddl file."""
    parser = Parser(str(domain.path), str(path))
    return _from_parsed(domain, parser.parse_problem(domain.pp))


def parse_problem_text(domain, text):
    parser = Parser(str(domain.path))
    parser.probInput = text
    return _from_parsed(domain, parser.parse_problem(domain.pp, read_from_file=False))


def problem_text(domain, name, object_types, init, goal):
    """PDDL text for a problem given as atoms. Static type atoms are implied by the object types."""
    if not isinstance(object_types, dict):
        object_types = {o: "object" for o in object_types}
    groups = {}
    for obj, tname in object_types.items():
        groups.setdefault(tname, []).append(obj)
    if list(groups) == ["object"]:
        objs = " ".join(groups["object"])
    else:
        objs = " ".join(" ".join(names) + f" - {t}" for t, names in groups.items())
    fluents = sorted(a for a in init if not a[0].startswith((TYPE_PREFIX,) + DERIVED_PREFIXES))
    return (
        f"(define (problem {name})\n  (:domain {domain.name})\n  (:objects {objs})\n"
        f"  (:init {' '.join(fact(*a) for a in fluents)})\n"
        f"  (:goal (and {' '.join(fact(*a) for a in sorted(goal))})))\n"
    )


def problem_from_atoms(domain, name, object_types, init, goal, save_to=None):
    """Build a problem from atoms by writing it as PDDL and reading it back, so every problem the system
    runs on has gone through the same parser as a hand-written .pddl file. Optionally save the text."""
    text = problem_text(domain, name, object_types, init, goal)
    if save_to is not None:
        Path(save_to).parent.mkdir(parents=True, exist_ok=True)
        Path(save_to).write_text(text)
    return parse_problem_text(domain, text)
