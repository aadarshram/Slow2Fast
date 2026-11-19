"""Operator model of the default domain, read from its PDDL file (domains/blocksworld/domain.pddl).

Kept as module-level names for older code that imports OPERATORS directly, but nothing is written by
hand here any more: the operators are compiled from the PDDL domain by slow2fast/pddl.py.
Lifted parameter slots are ?0, ?1, ... in action-argument order.
"""

from pathlib import Path

from slow2fast.pddl import PddlDomain

DOMAIN_FILE = Path(__file__).resolve().parents[1] / "domains" / "blocksworld" / "domain.pddl"
DOMAIN = PddlDomain(DOMAIN_FILE)
OPERATORS = DOMAIN.operators


def ground_ops(action):
    """Ground pre/add/delete for a concrete action using the operator model."""
    return DOMAIN.ground_ops(action)


def lifted_preconditions(action_name, param_vars):
    """Operator preconditions with action parameters renamed to param_vars."""
    spec = OPERATORS[action_name]
    if len(param_vars) != spec["arity"]:
        raise ValueError("param arity mismatch")
    binding = {f"?{i}": param_vars[i] for i in range(spec["arity"])}
    return [(pred, tuple(binding[s] for s in slots)) for pred, slots in spec["pre"]]


def add_effects(action):
    pre, add, delete = ground_ops(action)
    return add
