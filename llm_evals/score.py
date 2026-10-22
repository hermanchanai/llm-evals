"""Deterministic scoring. No LLM judges anything here.

Rent tolerances match the rent scraper's own golden-set grader:
    rent_min / rent_max   within max(3%, $50)
    sf_min  / sf_max      within max(5%, 60 sf)   (null == null is a match)
    available/coming_soon exact
    concession_weeks      exact (null == null is a MATCH)
    bed coverage          precision and recall over bed groups

Severity taxonomy matches the permit pipeline's classifier comparator:
    pass | miss | hallucination | field_drift
`hallucination` (gold is null, model returned a confident value) counts as an
incorrect field and is also reported separately: a fabricated "0 available" reads
as "sold out" to a rental underwrite, while a null is only a gap.
"""
from __future__ import annotations

from dataclasses import dataclass, field

RENT_TOL_PCT, RENT_TOL_ABS = 0.03, 50
SF_TOL_PCT, SF_TOL_ABS = 0.05, 60
RENT_FIELDS = ("rent_min", "rent_max")
SF_FIELDS = ("sf_min", "sf_max")
GRADED = RENT_FIELDS + SF_FIELDS + ("available", "coming_soon")


@dataclass
class FieldDiff:
    scope: str
    field: str
    expected: object
    actual: object
    passed: bool
    severity: str
    note: str = ""


@dataclass
class CaseScore:
    fixture_id: str
    diffs: list[FieldDiff] = field(default_factory=list)
    bed_recall_hit: int = 0
    bed_recall_tot: int = 0
    bed_precision_hit: int = 0
    bed_precision_tot: int = 0
    parse_error: str = ""

    @property
    def graded(self):   return [d for d in self.diffs if d.severity != "ungraded"]
    @property
    def n_pass(self):   return sum(1 for d in self.graded if d.passed)
    @property
    def n_total(self):  return len(self.graded)
    @property
    def n_hallucination(self): return sum(1 for d in self.diffs if d.severity == "hallucination")
    @property
    def n_miss(self):   return sum(1 for d in self.diffs if d.severity == "miss")
    @property
    def strict(self):   return self.n_total > 0 and self.n_pass == self.n_total and not self.parse_error


def _num_ok(exp, act, pct, ab) -> bool:
    return abs(exp - act) <= max(abs(exp) * pct, ab)


def _cmp(scope: str, name: str, exp, act, pct, ab) -> FieldDiff:
    if exp is None and act is None:
        return FieldDiff(scope, name, exp, act, True, "pass", "null == null")
    if exp is None:
        # Gold says this is not knowable from the page. A value here is fabricated.
        return FieldDiff(scope, name, exp, act, False, "hallucination")
    if act is None:
        return FieldDiff(scope, name, exp, act, False, "miss")
    if type(act) not in (int, float):
        return FieldDiff(scope, name, exp, act, False, "field_drift", "non-numeric")
    ok = _num_ok(exp, act, pct, ab)
    return FieldDiff(scope, name, exp, act, ok, "pass" if ok else "field_drift")


def validate_rent(pred) -> str:
    """Validate the task schema before grading; bool is not a JSON integer."""
    if not isinstance(pred, dict) or "units" not in pred or "concession_weeks" not in pred:
        return "expected object with units and concession_weeks"
    units = pred["units"]
    if not isinstance(units, list):
        return "units must be an array"
    seen = set()
    for unit in units:
        if not isinstance(unit, dict) or not all(k in unit for k in ("beds",) + GRADED):
            return "unit missing required fields"
        beds = unit["beds"]
        if type(beds) is not int or not 0 <= beds <= 6 or beds in seen:
            return "invalid or duplicate beds"
        seen.add(beds)
        for name in GRADED:
            value = unit[name]
            if value is None and name != "coming_soon":
                continue
            if type(value) is not int or value < 0:
                return f"invalid {name}: expected nonnegative integer"
        for low, high in (("sf_min", "sf_max"), ("rent_min", "rent_max")):
            if unit[low] is not None and unit[high] is not None and unit[low] > unit[high]:
                return f"invalid range {low}/{high}"
    weeks = pred["concession_weeks"]
    if weeks is not None and (type(weeks) is not int or weeks < 0):
        return "invalid concession_weeks"
    return ""


def score_rent(fixture_id: str, gold: dict, pred: dict | None,
               parse_error: str = "") -> CaseScore:
    problem = parse_error or validate_rent(pred)
    cs = CaseScore(fixture_id=fixture_id, parse_error=problem)
    if problem:
        cs.bed_recall_tot = len(gold["units"])
        for unit in gold["units"]:
            for name in GRADED:
                cs.diffs.append(FieldDiff(f"beds={unit['beds']}", name,
                                          unit.get(name), None, False, "miss", problem))
        cs.diffs.append(FieldDiff("community", "concession_weeks",
                                  gold.get("concession_weeks"), None, False, "miss", problem))
        return cs

    g_by_bed = {u["beds"]: u for u in gold["units"]}
    p_units = pred.get("units") or []
    p_by_bed: dict[int, dict] = {}
    for u in p_units:
        b = u.get("beds")
        if isinstance(b, int) and b not in p_by_bed:
            p_by_bed[b] = u

    # bed coverage
    cs.bed_recall_tot = len(g_by_bed)
    cs.bed_recall_hit = sum(1 for b in g_by_bed if b in p_by_bed)
    cs.bed_precision_tot = len(p_by_bed)
    cs.bed_precision_hit = sum(1 for b in p_by_bed if b in g_by_bed)

    for b, g in sorted(g_by_bed.items()):
        p = p_by_bed.get(b)
        scope = f"beds={b}"
        if p is None:
            for f in GRADED:
                if g.get(f) is None:
                    cs.diffs.append(FieldDiff(scope, f, None, None, False, "miss", "bed group absent"))
                else:
                    cs.diffs.append(FieldDiff(scope, f, g.get(f), None, False, "miss", "bed group not returned"))
            continue
        for f in SF_FIELDS:
            cs.diffs.append(_cmp(scope, f, g.get(f), p.get(f), SF_TOL_PCT, SF_TOL_ABS))
        for f in RENT_FIELDS:
            cs.diffs.append(_cmp(scope, f, g.get(f), p.get(f), RENT_TOL_PCT, RENT_TOL_ABS))
        for f in ("available", "coming_soon"):
            cs.diffs.append(_cmp(scope, f, g.get(f), p.get(f), 0.0, 0))

    # bed groups the model invented
    for b in sorted(set(p_by_bed) - set(g_by_bed)):
        cs.diffs.append(FieldDiff(f"beds={b}", "bed_group", None, b, False,
                                  "hallucination", "bed group not on the page"))

    ge, pe = gold.get("concession_weeks"), pred.get("concession_weeks")
    if ge is None and pe is None:
        cs.diffs.append(FieldDiff("community", "concession_weeks", ge, pe, True, "pass", "null == null"))
    elif ge is None:
        cs.diffs.append(FieldDiff("community", "concession_weeks", ge, pe, False, "hallucination"))
    elif pe is None:
        cs.diffs.append(FieldDiff("community", "concession_weeks", ge, pe, False, "miss"))
    else:
        cs.diffs.append(FieldDiff("community", "concession_weeks", ge, pe, ge == pe,
                                  "pass" if ge == pe else "field_drift"))
    return cs


VALID_CLASSES = {"single_family", "townhome", "multifamily", "mixed", "commercial", "unknown"}


def normalize_class(raw: str) -> str:
    """Permit output must be one enum. Invalid text must not pass unknown gold."""
    value = (raw or "").strip().lower().strip(".`\"'")
    return value if value in VALID_CLASSES else "invalid_output"
