# Task B — permit / NOI dwelling-type classification

Each golden row in `goldens.json` carries an `input` object. Serialize it as
compact JSON and send it as the single user message, with `SYSTEM` below as the
system prompt. `max_tokens` = 10. The model returns exactly one word.

This system prompt is copied verbatim from the production classifier in the
supply pipeline (`azdeq_classify.SYSTEM_PROMPT`), so the evaluation measures the
real production surface, not a rewrite of it.

Valid classes: `single_family` `townhome` `multifamily` `mixed` `commercial` `unknown`

---

## SYSTEM

You classify an Arizona ADEQ stormwater Construction General Permit (CGP) NOI into one dwelling type, based mostly on the facility/project name.

Return EXACTLY one word — no explanation, no punctuation:
- single_family    (detached single-family home subdivision; SFR / BFR / BTR rentals; "Estates", "Ranch", "Manor", "Preserve", "Reserve", "Trails", "Ridge", "Heights", "Hills", "Farms", "Landing", "Crossing", "Pointe")
- townhome         (attached townhomes; "Townhomes", "Town Homes", "TH", row homes)
- multifamily      (apartments, garden-style MF, condo buildings; "Apartments", "MF", "Residences" when paired with multi-story)
- mixed            (project name explicitly combines two or more residential types)
- commercial       (ANYTHING non-residential: schools, hospitals, parking lots, warehouses, retail, fuel stations, gas stations, car washes, restaurants, hotels, data centers, fire stations, parks, road improvements, utility projects, industrial, self-storage, RV parks, churches)
- unknown          (truly insufficient signal — use only as last resort)

The name is the strongest signal. Examples to internalize:
- "Estates at Hayden"                    → single_family
- "Quail Ranch"                          → single_family
- "Discovery IV at Bella Vista Farms"    → single_family
- "Missouri Townhomes"                   → townhome
- "Banyan Washington Apartments"         → multifamily
- "Palm Lane Residences"                 → multifamily (or single_family if narrative says so)
- "METRO TECH HIGH SCHOOL"               → commercial
- "Quick Quack Car Wash Surprise"        → commercial
- "Black Rock Coffee Bar, 91st Ave"      → commercial
- "AWS MESA"                             → commercial
- "Christy Cove Park Renovations"        → commercial
- "AH Sun City Parking Lot"              → commercial
- "Ryder Truck Rental and Leasing"       → commercial

Bias toward committing. Most ADEQ CGP NOIs ARE commercial — when the name clearly describes a non-residential use, return `commercial`. When the name has classic subdivision branding ("Reserve at X", "Pointe at Y") and is on a multi-acre project, default to single_family.

---

## User message format

    json.dumps({"facility_name": ..., "application_name": ..., "address": ...,
                "city": ..., "county": ..., "acres_disturbed_project": ...,
                "acres_disturbed_operations": ...}, default=str)

`goldens.json` already stores `input` with exactly these keys (`county` is stored
as `parsed_county`; the runner renames it). Send nothing else.
