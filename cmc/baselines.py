"""Comparison baselines for the full mechanism (blocksworld only: cmc/induce.py reads the default
domain's operators from cmc.domain). The `Dedupe` variants add only one change: two rules proposing the
same action are agreement, not a clash."""

from cmc.induce import InducedLibrary, groundings


class _Dedupe:
    def propose(self, state, goal):
        found = {}
        for index, rule in enumerate(self.rules):
            if rule.confirmations >= self.threshold:
                for action in groundings(rule, state, goal):
                    found.setdefault(action, []).append(index)
        if len(found) != 1:
            return None
        action, idxs = next(iter(found.items()))
        return f"r{max(idxs, key=lambda i: self.rules[i].confirmations)}", action

    def diagnose(self, state, goal):
        practiced, unpracticed = set(), set()
        for rule in self.rules:
            hits = groundings(rule, state, goal)
            (practiced if rule.confirmations >= self.threshold else unpracticed).update(hits)
        if len(practiced) == 1:
            return "unique", list(practiced)
        if len(practiced) > 1:
            return "multi_match", list(practiced)
        if unpracticed:
            return "below_threshold", list(unpracticed)
        return "no_match", []


class InduceOnly(InducedLibrary):
    """Trace-guided induction without the add-condition step: the "induce-only" baseline."""

    def _add_conditions(self, *args, **kwargs):
        return None


class InduceOnlyDedupe(_Dedupe, InduceOnly):
    pass


class InduceAddDedupe(_Dedupe, InducedLibrary):
    pass
