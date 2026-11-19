"""Random multi-tower blocksworld problems and the ckpt3 train / test schedule."""

import itertools
import random
import re
import string
from pathlib import Path

from cmc.blocksworld import Problem, complete_goal, state_from_towers
from cmc.curriculum import SkillLibrary, run_skill_episode

PHASES = ("single", "multi", "partial", "random")
MODES = ("train", "test")

ROW = re.compile(
    r"^(?P<phase>\w+)\s+(?P<name>\S+)\s+blocks\s+(?P<blocks>\d+)\s+"
    r"reached\s+(?P<reached>\d)\s+sources\s+(?P<sources>.+?)\s+"
    r"s1_ok\s+(?P<s1_ok>\d+)\s+s2_steps\s+(?P<s2_steps>\d+)\s+s1_bad\s+(?P<s1_bad>\d+)"
    r"(?:\s+s2_diag\s+(?P<s2_diag>\S+))?\s*$"
)
HEADER = re.compile(r"^mode\s+(?P<mode>train|test)\s+tasks\s+(?P<tasks>\d+)\s*$")
SUMMARY = re.compile(
    r"^s2_summary\s+no_match\s+(?P<no_match>\d+)\s+multi_match\s+(?P<multi_match>\d+)\s+"
    r"below_threshold\s+(?P<below_threshold>\d+)\s+loop_cut\s+(?P<loop_cut>\d+)\s*$"
)
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


def format_action(action):
    name, args = action
    return f"{name}({','.join(args)})"


def format_s2_diag(result):
    parts = []
    for step in result.steps:
        if step.source != "s2":
            continue
        reason = step.s2_reason or "unknown"
        parts.append(f"{reason}:{format_action(step.action)}")
    return ";".join(parts) if parts else "(none)"


def format_row(phase, name, problem, result):
    sources = " ".join(step.source for step in result.steps) or "(none)"
    return (
        f"{phase} {name} blocks {len(problem.blocks)} "
        f"reached {int(result.goal_reached)} sources {sources} "
        f"s1_ok {result.s1_ok} s2_steps {result.s2_steps} s1_bad {result.s1_bad} "
        f"s2_diag {format_s2_diag(result)}"
    )


def run_lessons(lessons, library, update):
    """Execute lessons; return rows with sources, reached, diags, and log line."""
    rows = []
    for phase, name, problem in lessons:
        result = run_skill_episode(problem, library, update=update)
        sources = [step.source for step in result.steps]
        diags = []
        for step in result.steps:
            if step.source != "s2":
                continue
            reason = step.s2_reason or "unknown"
            diags.append(f"{reason}:{format_action(step.action)}")
        rows.append(
            (phase, name, sources, result.goal_reached, diags, format_row(phase, name, problem, result))
        )
    return rows


def summarize_s2_reasons(rows):
    """Count s2 reasons from parse_log or run_lessons rows."""
    counts = {name: 0 for name in S2_REASONS}
    for row in rows:
        diags = row[4] if len(row) > 4 else []
        if isinstance(diags, str):
            continue
        for item in diags:
            reason = item.split(":", 1)[0]
            if reason in counts:
                counts[reason] += 1
    return counts


def rule_fingerprint(library):
    """Stable snapshot of rule identities and confirmation counts."""
    if library.known_rules:
        return tuple(sorted(library.counts().items()))
    rules = getattr(library, "rules", None)
    if rules is None:
        rules = getattr(library._impl, "rules", [])
    parts = []
    for rule in rules:
        parts.append((*rule.signature(), int(rule.confirmations)))
    return tuple(parts)


def figure_title(mode, tasks):
    if mode not in MODES:
        raise ValueError(f"unknown mode: {mode}")
    return f"Checkpoint 3 — {mode} · {tasks} tasks"


def format_log(mode, rows):
    if mode not in MODES:
        raise ValueError(f"unknown mode: {mode}")
    lines = [f"mode {mode} tasks {len(rows)}"]
    lines.extend(row[-1] for row in rows)
    counts = summarize_s2_reasons(rows)
    lines.append(
        "s2_summary "
        f"no_match {counts['no_match']} "
        f"multi_match {counts['multi_match']} "
        f"below_threshold {counts['below_threshold']} "
        f"loop_cut {counts['loop_cut']}"
    )
    return "\n".join(lines) + "\n"


def parse_log(text):
    """Parse a train/test log. Returns (mode, tasks, rows).

    Each row is (phase, name, sources, reached, diags).
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("empty log")
    header = HEADER.match(lines[0])
    if not header:
        raise ValueError(f"missing mode header: {lines[0]}")
    mode = header.group("mode")
    tasks = int(header.group("tasks"))
    rows = []
    for line in lines[1:]:
        if SUMMARY.match(line):
            continue
        match = ROW.match(line)
        if not match:
            raise ValueError(f"unparsed row: {line}")
        raw = match.group("sources").strip()
        sources = [] if raw == "(none)" else raw.split()
        diag_raw = match.groupdict().get("s2_diag")
        if not diag_raw or diag_raw == "(none)":
            diags = []
        else:
            diags = diag_raw.split(";")
        rows.append(
            (
                match.group("phase"),
                match.group("name"),
                sources,
                match.group("reached") == "1",
                diags,
            )
        )
    if tasks != len(rows):
        raise ValueError(f"header tasks {tasks} != rows {len(rows)}")
    return mode, tasks, rows


def run_mode(
    mode,
    n=4,
    practice=2,
    seed=0,
    random_count=None,
    test_count=None,
    known_rules=False,
    rules_path=None,
):
    """Shared train / test runner.

    train: curriculum with learning on; log every lesson; save rules if
    rules_path is set.
    test: load saved rules from rules_path (required), then frozen random
    holdout with learning off. No curriculum warmup.
    """
    if mode not in MODES:
        raise ValueError(f"unknown mode: {mode}")
    random_count = 100 if random_count is None else random_count
    test_count = 100 if test_count is None else test_count
    rules_path = Path(rules_path) if rules_path is not None else None

    if mode == "train":
        library = SkillLibrary(known_rules=known_rules)
        lessons = train_curriculum(
            n=n, practice=practice, seed=seed, random_count=random_count
        )
        rows = run_lessons(lessons, library, update=True)
        if rules_path is not None:
            library.save(rules_path)
    else:
        if rules_path is None:
            raise FileNotFoundError("test mode requires rules_path to saved rules")
        library = SkillLibrary.load(rules_path)
        holdout = test_holdout(n=n, seed=seed, count=test_count)
        rows = run_lessons(holdout, library, update=False)

    return format_log(mode, rows), library


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
