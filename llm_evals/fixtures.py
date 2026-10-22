"""Render rent fixtures from specs AND prove each one rolls up to the human gold.

    python -m llm_evals.fixtures --verify   # check only, exit 1 on mismatch
    python -m llm_evals.fixtures            # check, then rewrite tasks/rent_extraction/fixtures/

The verify step is the whole point: a fixture whose text cannot produce the human
gold label is a broken fixture, and would score every model wrong for the wrong
reason. Gold is never edited to match a spec.
"""
from __future__ import annotations

import argparse
import json

from llm_evals.specs import S
from llm_evals.tasks import RENT

GOLD = RENT / "gold"
FIX = RENT / "fixtures"


# --------------------------------------------------------------------- rollup
def rollup(spec: dict) -> list[dict]:
    """Bed-level rollup implementing the labeling conventions the gold follows."""
    ov = spec.get("gold_overrides", {})
    beds_seen, out = {}, []
    for p in spec["plans"]:
        if p.get("placeholder"):
            continue                                   # TEMP plan is dropped entirely
        b = p["beds"]
        g = beds_seen.setdefault(b, dict(beds=b, sf=[], rents=[], avail=0))
        if p.get("in_sf_band", True):
            g["sf"].append(p["sf"])
            if p.get("sf_max_display"):
                g["sf"].append(p["sf_max_display"])
        if p.get("counts_rent", True):
            if p["price_display"] == "plan_level":
                g["rents"].append(p["plan_price"])
            elif p["price_display"] in ("per_unit", "per_unit_range"):
                g["rents"] += [u["rent"] for u in p["units"] if u.get("rent") is not None]
        if p.get("counts_availability", True):
            # What a reader can actually recover from the page: the uncapped count
            # when the page publishes one, otherwise the rows it renders.
            rendered = p["units"][: p["rendered_cap"]] if p.get("rendered_cap") else p["units"]
            g["avail"] += p["true_count"] if p.get("true_count") else len(rendered)

    for b in sorted(beds_seen):
        g = beds_seen[b]
        rents = sorted(g["rents"])
        rmin = rents[0] if rents else None
        rmax = (rents[-1] if rents else None)
        if ov.get("rent_max_null"):
            rmax = None
        if ov.get("rents_ungraded"):
            rmin = rmax = None
        avail = None if ov.get("availability_ungraded") else g["avail"]
        out.append(dict(beds=b,
                        sf_min=min(g["sf"]) if g["sf"] else None,
                        sf_max=max(g["sf"]) if g["sf"] else None,
                        rent_min=rmin, rent_max=rmax,
                        available=avail, coming_soon=0))
    return out


def verify(fid: str, spec: dict) -> list[str]:
    gold = json.loads((GOLD / f"{fid}.json").read_text())
    got, want = rollup(spec), gold["units"]
    errs = []
    # A capped plan must publish its uncapped count somewhere a reader can see it.
    for p in spec["plans"]:
        if p.get("rendered_cap") and not p.get("true_count"):
            errs.append(f"  plan {p['name']}: rendered_cap set with no true_count -> "
                        "gold availability is unrecoverable from the page text")
    # Every non-null gold number must appear verbatim in the rendered page text.
    text = render(fid, spec)
    for grp in want:
        for k in ("sf_min", "sf_max", "rent_min", "rent_max"):
            v = grp.get(k)
            if v is None:
                continue
            if f"{v:,}" not in text and str(v) not in text:
                errs.append(f"  beds={grp.get('beds')} {k}={v}: not present in rendered text")
    for p in spec["plans"]:
        if p.get("true_count") and str(p["true_count"]) not in text:
            errs.append(f"  plan {p['name']}: true_count={p['true_count']} never "
                        "printed on the page -> gold availability is unrecoverable")
    if len(got) != len(want):
        errs.append(f"  bed-group count: rollup={len(got)} {[g['beds'] for g in got]} "
                    f"!= gold={len(want)} {[g['beds'] for g in want]}")
        return errs
    for a, b in zip(got, want):
        for k in ("beds", "sf_min", "sf_max", "rent_min", "rent_max", "available"):
            if a[k] != b.get(k):
                errs.append(f"  beds={b.get('beds')} {k}: rollup={a[k]!r} != gold={b.get(k)!r}")
    return errs


# --------------------------------------------------------------------- render
def _money(v):
    return f"${v:,.2f}"


def _sf(v):
    return f"{v:,}"


def render(fid: str, spec: dict) -> str:
    L = [f"{spec['community_name']}", "=" * len(spec["community_name"]), ""]
    for b in spec.get("banners", []):
        L += [b, ""]
    L += ["Floor Plans & Availability", ""]

    for p in spec["plans"]:
        head = f"{p['name']} — {_beds(p['beds'])} | {p['baths']} Bath | "
        head += (f"{_sf(p['sf'])}-{_sf(p['sf_max_display'])} Sq Ft"
                 if p.get("sf_max_display") else f"{_sf(p['sf'])} Sq Ft")
        L.append(head)
        if p.get("live_work"):
            L.append("  Type: Live/Work Units — Office or Business Space!")
        if p.get("badge"):
            L.append(f"  {p['badge']}")
        pd = p["price_display"]

        if pd == "contact":
            L.append("  Contact Us")
        elif pd == "call_for_pricing":
            L.append("  Call for Pricing")
        elif pd == "plan_level":
            L.append(f"  {_money(p['plan_price'])}")
            L.append("  Contact Us for availability")
        else:
            units = p["units"][: p["rendered_cap"]] if p.get("rendered_cap") else p["units"]
            for u in units:
                row = f"  Apartment #{u['no']}"
                if u.get("sf_note"):
                    row += f" ({u['sf_note']})"
                if pd == "per_unit_range":
                    row += f"   {_money(u['rent'])} - {_money(u['rent_high'])}"
                elif u.get("rent") is not None:
                    if spec.get("fee_addon"):
                        row += (f"   Total Monthly Leasing Price Starting at: "
                                f"{_money(u['rent'] + spec['fee_addon'])}"
                                f"   ·   Base rent {_money(u['rent'])}")
                    else:
                        row += f"   {_money(u['rent'])}"
                _d = u.get("date", "Now")
                row += f"   ·   {'Available ' + _d if _d != 'Now' else 'Available Now'}"
                L.append(row)
            if p.get("rendered_cap") and len(p["units"]) > p["rendered_cap"]:
                L.append(f"  Showing {p['rendered_cap']} of {p.get('true_count')}")
        L.append("")

    for f in spec.get("footer", []):
        L.append(f)
    if spec.get("fee_addon"):
        L += ["", f"Total Monthly Leasing Price includes {_money(spec['fee_addon'])} of mandatory "
                  "trash, pest, internet and utility-administration fees."]
    return "\n".join(L).rstrip() + "\n"


def _beds(b):
    return "Studio" if b == 0 else f"{b} Bedroom" + ("" if b == 1 else "s")


# ----------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    bad = 0
    for fid in sorted(S):
        errs = verify(fid, S[fid])
        if a.verify:
            saved = FIX / f"{fid}.txt"
            if not saved.is_file() or saved.read_text() != render(fid, S[fid]):
                errs.append("  saved fixture is missing or differs from verified renderer")
        if errs:
            bad += 1
            print(f"FAIL {fid}")
            print("\n".join(errs))
        else:
            print(f"ok   {fid}")
    if bad:
        print(f"\n{bad}/{len(S)} fixtures do NOT roll up to gold — fix the SPEC, never the gold.")
        return 1
    print(f"\nall {len(S)} specs roll up to human gold")
    if not a.verify:
        FIX.mkdir(parents=True, exist_ok=True)
        for fid in sorted(S):
            (FIX / f"{fid}.txt").write_text(render(fid, S[fid]))
        print(f"wrote {len(S)} fixtures -> {FIX}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
