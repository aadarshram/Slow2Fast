"""Train / frozen-test protocol over lists of PddlProblem, with audit metrics. Domain-independent."""

import os
import sys

from slow2fast.generate import S2_REASONS
from slow2fast.pddl import problem_from_atoms
from slow2fast.system2 import System2, run_episode, run_s1_only


def ensure_deterministic():
    """Re-exec once with PYTHONHASHSEED=0. pyperplan's heuristics iterate Python sets of strings, whose
    order depends on the per-process hash seed, so without this two runs of the same experiment can
    differ in every System 2 tie-break. Call at the top of a script's main()."""
    if os.environ.get("PYTHONHASHSEED") != "0":
        os.environ["PYTHONHASHSEED"] = "0"
        os.execv(sys.executable, [sys.executable] + sys.argv)


class NullLibrary:
    """No rules: every step goes to System 2. Used to price a pure System 2 run."""

    rules = ()

    def propose(self, state, goal):
        return None

    def diagnose(self, state, goal):
        return "no_match", []

    def observe(self, *args, **kwargs):
        return None

    def note_success(self, name):
        return None


_dist = {}
_AUDIT = System2("bfs")  # its counters are ignored: this search is measurement, not part of any run


def distance(problem, state):
    """Exact distance to the goal (pyperplan BFS). Used only to audit results; never shown to a learner
    or to the System 2 being measured. tests/test_pddl.py checks it against an independent search."""
    key = (problem, state)
    if key not in _dist:
        plan = _AUDIT._solve(problem, state, "bfs")
        _dist[key] = None if plan is None else len(plan)
    return _dist[key]


def audit(problem, result):
    """Replay an episode; count System 1 steps that strictly reduce the exact distance to the goal, and
    those that move into a state from which the goal is unreachable (an irreversible mistake)."""
    inf = float("inf")
    state, good, total, dead = problem.initial, 0, 0, 0
    for step in result.steps:
        nxt = problem.domain.apply(state, step.action)
        if step.source == "s1":
            total += 1
            before, after = distance(problem, state), distance(problem, nxt)
            before = inf if before is None else before
            after = inf if after is None else after
            good += int(after < before)
            dead += int(after == inf and before < inf)
        state = nxt
    return good, total, dead


def lessons_to_problems(domain, lessons, tag):
    """Generator lessons [(phase, name, Problem)] -> parsed PddlProblems (via PDDL text)."""
    return [
        problem_from_atoms(domain, f"{tag}-{i}-{phase}", p.blocks, p.initial, p.goal)
        for i, (phase, _name, p) in enumerate(lessons)
    ]


def share(sources):
    return sources.count("s1") / max(1, len(sources))


def evaluate(library_factory, kind, train, test, audit_results=True):
    library, s2 = library_factory(), System2(kind)
    if hasattr(train, "run"):  # an adaptive training schedule, rather than a plain list of problems
        train_sources = train.run(library, s2)
    else:
        train_sources = []
        for problem in train:
            result = run_episode(problem, library, s2, update=True)
            train_sources += [step.source for step in result.steps]
    test_s2 = System2(kind)
    reasons = {k: 0 for k in S2_REASONS}
    reached = good = total = steps = optimal_steps = s1 = dead = 0
    for problem in test:
        result = run_episode(problem, library, test_s2, update=False)
        reached += int(result.goal_reached)
        if audit_results:
            g, t, dd = audit(problem, result)
            good, total, dead = good + g, total + t, dead + dd
            optimal_steps += distance(problem, problem.initial)
        steps += len(result.steps)
        s1 += result.s1_ok
        for step in result.steps:
            if step.source == "s2":
                reasons[step.s2_reason or "unknown"] = reasons.get(step.s2_reason or "unknown", 0) + 1
    s1_alone = sum(int(run_s1_only(problem, library)) for problem in test)
    return {
        "s1_alone": s1_alone,
        "train": share(train_sources),
        "test": s1 / max(1, steps),
        "prec": good / max(1, total) if audit_results else float("nan"),
        "dead_ends": dead,
        "rules": len(library.rules),
        "reach": reached,
        "tasks": len(test),
        "reasons": reasons,
        "work": test_s2.work,
        "expansions": test_s2.expansions,
        "evals": test_s2.evals,
        "overhead": steps / max(1, optimal_steps) if audit_results else float("nan"),
        "library": library,
    }


def pure_system2_work(kind, test):
    s2, library = System2(kind), NullLibrary()
    for problem in test:
        run_episode(problem, library, s2, update=False)
    return s2.work
