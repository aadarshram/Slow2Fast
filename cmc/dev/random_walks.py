"""Random-walk training problems (Fern, Yoon, Givan, ICAPS 2004): a curriculum with no hand-built phases.

A problem is made from an example problem (a "template") by walking:
  1. start from the template's initial state, scrambled by a few random applicable actions;
  2. take `steps` more uniformly random applicable actions;
  3. the goal is what is true at the end of the walk, restricted to the predicates that appear in the template's
     goal (optionally only a random fraction of those atoms, for partial goals).
The goal holds at the end of a path from the start, so every such problem is solvable. Short walks give easy,
local goals; long walks give goals far from the start.

WalkTraining turns this into a training schedule that adapts to how System 1 is doing: it lengthens the walk when
System 1 has been taking most of the steps and shortens it when it falls behind (thresholds tau and delta as in
the paper). To avoid stalling at one length it also advances after `patience` problems.

Nothing here knows about a particular domain: it needs only the operators and a few example problems (any sizes).
Known limits (from the paper): goals that need an ordering of events (doors and keys) are unlikely to come out of
a random walk, and in domains with dead ends the walk distribution can differ a lot from the real task distribution.
"""

import math
import statistics
from collections import deque
import random

from cmc.pddl import TYPE_PREFIX, problem_from_atoms
from cmc.system2 import run_episode


def goal_predicates(template):
    return {pred for pred, _args in template.goal}


def random_walk(domain, state, objects, steps, rng):
    """`steps` uniformly random applicable actions from `state` (fewer if it has no applicable action)."""
    state = frozenset(state)
    for _ in range(steps):
        actions = domain.applicable_actions(state, objects)
        if not actions:
            break
        state = domain.apply(state, rng.choice(actions))
    return state


def walk_problem(domain, templates, steps, rng, name="walk", scramble=4, goal_fraction=1.0, tries=25):
    """One random-walk problem, or None if no try produced a goal that is not already satisfied."""
    for _ in range(tries):
        template = rng.choice(templates)
        wanted = goal_predicates(template)
        start = random_walk(domain, template.initial, template.objects, scramble, rng)
        end = random_walk(domain, start, template.objects, steps, rng)
        atoms = sorted(a for a in end if a[0] in wanted)
        open_atoms = [a for a in atoms if a not in start]
        if not open_atoms:
            continue  # the walk achieved nothing the goal predicates can see
        if goal_fraction < 1.0:
            keep = [a for a in atoms if rng.random() < goal_fraction]
            if not any(a in open_atoms for a in keep):
                keep.append(rng.choice(open_atoms))  # never a goal that is already satisfied
            atoms = sorted(set(keep))
        init = {a for a in start if not a[0].startswith(TYPE_PREFIX)}  # type atoms are re-added from the objects
        return problem_from_atoms(domain, name, template.object_types, init, set(atoms))
    return None


class WalkTraining:
    """Adaptive random-walk curriculum. `run(library, s2)` trains on up to `budget` problems and returns the
    source ("s1"/"s2") of every step taken, like the list-of-problems training loop does. `history` records
    (walk length, System 1 share) per problem."""

    def __init__(self, domain, templates, budget, seed=0, n_start=1, n_max=40, tau=0.9, delta=0.1, window=5,
                 patience=20, growth=1.5, scramble=4, goal_fraction=1.0):
        self.domain, self.templates, self.budget = domain, list(templates), budget
        self.rng = random.Random(seed)
        self.n_start, self.n_max, self.tau, self.delta = n_start, n_max, tau, delta
        self.window, self.patience, self.growth = window, patience, growth
        self.scramble, self.goal_fraction = scramble, goal_fraction
        self.history = []

    def next_length(self, n, recent, since):
        """The walk length to use next, from the recent System 1 shares: longer when System 1 is on top of it,
        shorter when it has fallen behind a longer walk, and longer anyway after `patience` problems at one
        length (so a weak System 1 cannot stall the schedule at the shortest walks)."""
        if len(recent) < self.window:
            return n
        average = statistics.mean(recent)
        if average >= self.tau:
            return min(self.n_max, max(n + 1, math.ceil(n * self.growth)))
        if average <= self.tau - self.delta and n > self.n_start:
            return max(self.n_start, math.floor(n / self.growth))
        if since >= self.patience:
            return min(self.n_max, max(n + 1, math.ceil(n * self.growth)))
        return n

    def run(self, library, s2):
        sources, recent, n, since, trained, attempts = [], deque(maxlen=self.window), self.n_start, 0, 0, 0
        while trained < self.budget and attempts < 5 * self.budget:
            attempts += 1
            problem = walk_problem(self.domain, self.templates, n, self.rng, f"walk-{attempts}", self.scramble,
                                   self.goal_fraction)
            if problem is None:
                continue
            result = run_episode(problem, library, s2, update=True)
            steps = [step.source for step in result.steps]
            sources += steps
            share = steps.count("s1") / len(steps) if steps else 1.0
            self.history.append((n, share))
            recent.append(share)
            trained += 1
            since += 1
            new_n = self.next_length(n, recent, since)
            if new_n != n:
                n = new_n
                recent.clear()
                since = 0
        return sources
