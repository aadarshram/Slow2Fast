"""System 2 = a standard PDDL planner (pyperplan), plus cost accounting and an episode runner.

kind="ehc": pyperplan enforced hill-climbing (`ehs`) with the hFF heuristic. Satisficing, incomplete.
kind="bfs": pyperplan breadth-first search. Exact (shortest plans).

Both plan on pyperplan's grounded task for the problem; for each call the task is re-rooted at the
current state. Nothing here is domain-specific.

pyperplan's hill-climbing returns plans with detours, and only the first action is executed before replanning,
so the returned plan is post-processed by cutting cycles (a state visited twice: drop the steps between the
visits). This is the same loop cutting the earlier planner did; it never changes what the library found
beyond removing the cycle.

Cost is counted inside the library's own loops:
  expansions  states whose successors were generated (Task.get_successor_states calls)
  evals       heuristic evaluations (ehc only)
`work` = expansions + evals.

For "bfs", `optimal` is a lazy judge: optimal(action) is True when that action starts some shortest plan,
decided by one more BFS from the successor state. It is only invoked by a learner when it needs to know
whether a competing proposal was acceptable, and that search is counted in the same cost.
"""

from pyperplan.heuristics.relaxation import hFFHeuristic
from pyperplan.search.breadth_first_search import breadth_first_search
from pyperplan.search.enforced_hillclimbing_search import enforced_hillclimbing_search
from pyperplan.task import Task

from slow2fast.episode import EpisodeResult, Step
from slow2fast.pddl import fact, parse_fact


class BudgetExceeded(Exception):
    """A System 2 call used more expansions than its budget allows."""


class _CountingTask(Task):
    def __init__(self, base, state, owner):
        super().__init__(base.name, base.facts, state, base.goals, base.operators)
        self._owner = owner

    def get_successor_states(self, state):
        self._owner.expansions += 1
        if self._owner.budget is not None and self._owner.expansions - self._owner._call_start > self._owner.budget:
            raise BudgetExceeded()
        return super().get_successor_states(state)


class _CountingHeuristic:
    def __init__(self, heuristic, owner):
        self._h, self._owner = heuristic, owner

    def __call__(self, node):
        self._owner.evals += 1
        return self._h(node)


class System2:
    def __init__(self, kind="ehc", budget=None):
        """budget: optional cap on expansions per plan() call; a call over budget returns None. Meant for
        screening generated problems; experiments run System 2 without a budget."""
        if kind not in ("ehc", "bfs"):
            raise ValueError(f"unknown System 2: {kind}")
        self.kind = kind
        self.budget = budget
        self._call_start = 0
        self.expansions = 0
        self.evals = 0
        self.calls = 0
        self.optimal = None
        self._bfs_len = {}

    @property
    def work(self):
        return self.expansions + self.evals

    def _task_at(self, problem, state):
        base = problem.ground_task()
        facts = frozenset(fact(*a) for a in state if fact(*a) in base.facts)
        return base, _CountingTask(base, facts, self)

    def _solve(self, problem, state, kind):
        base, task = self._task_at(problem, state)
        if kind == "bfs":
            solution = breadth_first_search(task)
        else:
            heuristic = problem._heuristics.get("hff")
            if heuristic is None:
                heuristic = problem._heuristics["hff"] = hFFHeuristic(base)
            solution = enforced_hillclimbing_search(task, _CountingHeuristic(heuristic, self))
        if solution is None:
            return None
        return [parse_fact(op.name) for op in solution]

    def is_dead(self, problem, state):
        """True when the goal is unreachable from `state`. Exact for bfs. For ehc it can only use the relaxed
        reachability test (hFF is infinite), which is sound but misses dead ends that need deletes to see."""
        state = frozenset(state)
        if self.kind == "bfs":
            return self._solve(problem, state, "bfs") is None
        base = problem.ground_task()
        heuristic = problem._heuristics.get("hff") or problem._heuristics.setdefault("hff", hFFHeuristic(base))
        _base, task = self._task_at(problem, state)
        self.evals += 1
        from pyperplan.search.searchspace import make_root_node

        return heuristic(make_root_node(task.initial_state)) == float("inf")

    def plan(self, problem, state):
        """A plan (list of (name, args)) from `state`, or None. The first action is what gets executed."""
        self.calls += 1
        self.optimal = None
        self._call_start = self.expansions
        state = frozenset(state)
        try:
            plan = self._solve(problem, state, self.kind)
        except BudgetExceeded:
            return None
        if plan and self.kind == "ehc":
            plan = cut_loops(problem.domain, state, plan)
        if plan and self.kind == "bfs":
            self.optimal = self._judge(problem, state, len(plan))
        return plan

    def _judge(self, problem, state, length):
        def optimal(action):
            key = (problem, state, action)
            if key not in self._bfs_len:
                try:
                    nxt = problem.domain.apply(state, action)
                except ValueError:
                    self._bfs_len[key] = False
                    return False
                if problem.domain.goal_holds(nxt, problem.goal):
                    self._bfs_len[key] = length == 1
                else:
                    rest = self._solve(problem, nxt, "bfs")
                    self._bfs_len[key] = rest is not None and len(rest) == length - 1
            return self._bfs_len[key]

        return optimal


def cut_loops(domain, state, plan):
    """Remove cycles from a plan: when a state repeats, drop the steps taken between the two visits."""
    visited, kept, current = [state], [], state
    for action in plan:
        nxt = domain.apply(current, action)
        if nxt in visited:
            back = visited.index(nxt)
            kept = kept[:back]
            visited = visited[: back + 1]
            current = visited[-1]
        else:
            kept.append(action)
            visited.append(nxt)
            current = nxt
    return kept


def _blame_dead_end(problem, trace, s2, library):
    """System 2 found no plan from the current state. Dead-ness cannot be undone, so along the episode the
    states fall into "alive ... alive | dead ... dead". Binary-search the first dead state and, if System 1
    took the step that entered it, record that step as a bad outcome for the rules that proposed it."""
    if not trace or not s2.is_dead(problem, trace[-1][3]):
        return  # System 2 failed but the state is not provably dead: nothing to learn from
    lo, hi = 0, len(trace) - 1  # first index whose resulting state is dead
    while lo < hi:
        mid = (lo + hi) // 2
        if s2.is_dead(problem, trace[mid][3]):
            hi = mid
        else:
            lo = mid + 1
    before, action, source, _after, voters = trace[lo]
    if source == "s1":
        library.record_outcome(before, problem.goal, action, voters, "dead_end")


def run_s1_only(problem, library):
    """System 1 alone, no fallback: True if rules reach the goal without ever refusing or revisiting a state."""
    domain = problem.domain
    state = frozenset(problem.initial)
    seen = {state}
    for _ in range(8 * max(1, len(problem.objects))):
        if domain.goal_holds(state, problem.goal):
            return True
        proposal = library.propose(state, problem.goal)
        if proposal is None:
            return False
        nxt = domain.apply(state, proposal[1])
        if nxt in seen:
            return False
        seen.add(nxt)
        state = nxt
    return domain.goal_holds(state, problem.goal)


def run_episode(problem, library, s2, update):
    """One task. A practiced rule may act; otherwise System 2 plans and its first action is executed.

    With a library that learns from outcomes (update=True), every step is kept in a short trace; a System 1
    proposal that would revisit a state is recorded as a "loop" outcome, and when System 2 later finds the
    task unsolvable, the first System 1 step that entered the doomed region is recorded as a "dead_end".
    If the library also spot-checks (audit_rate > 0, exact System 2 only), some System 1 proposals are checked
    against System 2 while learning: a worse action is recorded as "wrong" and System 2's action is taken."""
    domain = problem.domain
    outcomes = update and getattr(library, "learns_outcomes", False)
    state = frozenset(problem.initial)
    seen = {state}
    trace = []  # (state before, action, source, state after, voter rule ids)
    result = EpisodeResult()
    bound = 8 * max(1, len(problem.objects))
    while not domain.goal_holds(state, problem.goal) and len(result.steps) < bound:
        proposal = library.propose(state, problem.goal)
        reason = None
        plan = None
        if proposal is not None:
            name, action = proposal
            nxt = domain.apply(state, action)
            voters = library.voters(state, problem.goal, action) if outcomes else []
            if nxt not in seen and outcomes and s2.kind == "bfs" and library.audit_due():
                plan = s2.plan(problem, state)  # learning-time spot check; never done when System 1 decides
                if plan and not library.audit_ok(state, problem.goal, action, plan[0], s2.optimal):
                    library.record_outcome(state, problem.goal, action, voters, "wrong")
                    reason = "audit_wrong"
                else:
                    plan = None  # System 1 was right: let it act
            if reason is None and nxt not in seen:
                result.steps.append(Step("s1", action))
                result.s1_ok += 1
                if update:
                    library.note_success(name)
                if outcomes:
                    trace.append((state, action, "s1", nxt, voters))
                seen.add(nxt)
                state = nxt
                continue
            if reason is None:
                reason = "loop_cut"
                if outcomes:
                    library.record_outcome(state, problem.goal, action, voters, "loop")
        else:
            reason, _detail = library.diagnose(state, problem.goal)
        if plan is None:
            plan = s2.plan(problem, state)
        if not plan:
            if outcomes:
                _blame_dead_end(problem, trace, s2, library)
            break
        action = plan[0]
        nxt = domain.apply(state, action)
        result.steps.append(Step("s2", action, s2_reason=reason))
        result.s2_steps += 1
        if update:
            extra = {"optimal": s2.optimal} if getattr(library, "accepts_optimal", False) else {}
            library.observe(state, problem.goal, action, plan=plan, **extra)
        if outcomes:
            trace.append((state, action, "s2", nxt, []))
        seen.add(nxt)
        state = nxt
    result.goal_reached = domain.goal_holds(state, problem.goal)
    return result
