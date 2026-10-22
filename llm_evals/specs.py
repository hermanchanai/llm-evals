"""Structured source-of-truth for the rent fixtures.

Each spec renders to ONE page-text fixture and must roll up to the human gold
label in tasks/rent_extraction/gold/<id>.json. `python -m llm_evals.fixtures --verify`
proves that mechanically; a spec that disagrees with the gold is a BROKEN SPEC,
never a broken gold.

Provenance: every community, number and trap below is taken from the human gold
labels (read from the LIVE sites, with labeling notes) and from failure patterns
recorded in the rent scraper's adapter tests. Nothing here is invented.

Plan fields:
  in_sf_band            plan's SF counts toward the bed group's sf_min/sf_max. Default
                        True — an advertised plan counts even with no price and no
                        count ('Contact Us'). Set False ONLY for an affordable-PROGRAM
                        bucket spanning an SF range, or a plan the site segregates as
                        non-residential (Live/Work).
  price_display         per_unit | per_unit_range | plan_level | contact | call_for_pricing | quote_only
  units                 what the page lists (rent = BASE rent; rent_high = lease-term top)
  rendered_cap          page renders only the first N units (display cap trap)
  true_count            real availability when the page's rendered rows are capped
  counts_availability   plan contributes to `available`
  counts_rent           plan contributes to rent_min/rent_max
"""

S = {}

# ---------------------------------------------------------------- 1. baseline
S["avail_sandy_springs"] = dict(
    community_name="Avail Sandy Springs", platform="rentcafe",
    trap="none — clean per-unit tables, no concession banner. The floor: a model that misses here is disqualified.",
    banners=[],
    plans=[
        dict(name="A1", beds=1, baths=1, sf=520, price_display="per_unit",
             units=[dict(no="0213", rent=1320, date="9/7")]),
        dict(name="B1", beds=2, baths=2, sf=733, price_display="per_unit",
             units=[dict(no=f"0{n}", rent=r, date=d) for n, r, d in [
                 ("305",1356,"Now"),("308",1380,"Now"),("311",1395,"9/12"),("402",1410,"Now"),
                 ("405",1425,"9/20"),("408",1440,"Now"),("411",1455,"10/1"),("502",1470,"Now"),
                 ("505",1489,"9/15"),("508",1505,"Now"),("511",1520,"10/8"),("602",1545,"Now"),
                 ("605",1570,"9/28"),("608",1610,"Now"),("611",1655,"10/15"),("702",1700,"Now"),
                 ("705",1770,"11/1")]]),
    ],
    footer=["Floor Plans filter: A1 · B1"],
)

# ------------------------------------------- 2. conditional concession -> null
S["emblem_conyers"] = dict(
    community_name="Emblem Conyers", platform="sightmap",
    trap="Banner says 6 WEEKS FREE but conditions it on a NAMED BED TYPE ('Tour a 1-Bedroom'). Convention: a named-subset qualifier nulls the concession. Gold concession_weeks = null.",
    banners=["Your Key to 6 Weeks FREE. Tour a 1-Bedroom & Apply Within 24 Hours: App + Admin Fees Waived AND 6 Weeks FREE when you move in by 9/15!"],
    plans=[
        dict(name="A2", beds=1, baths=1, sf=774, price_display="per_unit", badge="12 available",
             units=[dict(no=n, rent=r, date=d) for n, r, d in [
                 ("104",1382,"Now"),("110",1382,"Now"),("118",1395,"Now"),("206",1405,"9/5"),
                 ("212",1412,"Now"),("218",1420,"Now"),("305",1432,"9/19"),("311",1440,"Now"),
                 ("317",1448,"Now"),("323",1455,"10/3"),("402",1464,"Now"),("408",1472,"Now")]]),
        dict(name="B1", beds=2, baths=2, sf=1099, price_display="per_unit", badge="Only 1 left!",
             units=[dict(no="301", rent=1695, date="Now")]),
        dict(name="B2", beds=2, baths=2, sf=1194, price_display="per_unit", badge="Only 3 left!",
             units=[dict(no=n, rent=r, date=d) for n, r, d in [
                 ("209",1740,"Now"),("309",1780,"9/26"),("409",1815,"Now")]]),
    ],
    footer=["Building map — Floor 1: 3 units · Floor 2: 4 units · Floor 3: 6 units · Floor 4: 3 units"],
)

# ------------------------------------ 3. plan-level only, availability ungraded
S["union_landing"] = dict(
    community_name="Union Landing Apartments", platform="realpage",
    trap="Three plans PUBLISHED, none bookable. Availability is UNGRADED (null, not 0) — a renter cannot determine it. rent_max null: only one price per plan is published. The 1BR must not vanish just because no unit is listed (the RealPage all-or-nothing bug).",
    banners=[],
    plans=[
        dict(name="1 Bedroom and 1 Bath", beds=1, baths=1, sf=841, price_display="plan_level", plan_price=1216, units=[]),
        dict(name="2 Bedroom and 2 Baths", beds=2, baths=2, sf=1068, price_display="plan_level", plan_price=1453, units=[]),
        dict(name="3 Bedroom and 2 Baths", beds=3, baths=2, sf=1240, price_display="plan_level", plan_price=1673, units=[]),
    ],
    footer=["Availability search: No floorplans found",
            "For more information on our availability and leasing, please fill out the Contact Us form.",
            "Our current reservation list is on a first come, first serve basis."],
    gold_overrides=dict(availability_ungraded=True, rent_max_null=True),
)

# --------------------------- 4. waitlist/Contact Us = 0, Live/Work SF exclusion
S["northbend"] = dict(
    community_name="Northbend", platform="entrata",
    trap="'Contact Us' plans are NO availability (0) with NULL rent — never available=1 with an indicative rent (the Entrata waitlist defect that put 1BR rent_max at $2,938 vs a true $1,800). Live/Work plans are segregated by the site's own filter and must NOT widen the SF bands (including X would push studio sf_max 535->1079). SF band = the full ADVERTISED plan set per bed, wider than the priced plans.",
    banners=["Move In by 8/31 & Receive 8 Weeks Free! Move In by 10/31 & Receive 6 Weeks Free! *Must sign a 14+month lease to qualify for rent specials*",
             "Apply Within 48 Hours of Initial Visit to Receive 1/2 Off Application & Administration Fees!",
             "Apply Same Day to Receive $250 Gift Card!"],
    plans=[
        dict(name="A", beds=0, baths=1, sf=407, price_display="per_unit",
             units=[dict(no="1104", rent=1422, date="Now")]),
        dict(name="B", beds=0, baths=1, sf=535, price_display="per_unit",
             units=[dict(no="2118", rent=1422, date="9/1")]),
        dict(name="C", beds=1, baths=1, sf=535, price_display="per_unit",
             units=[dict(no="2071", rent=1663, date="Now"), dict(no="3044", rent=1690, date="9/12")]),
        dict(name="H", beds=1, baths=1, sf=812, price_display="per_unit",
             units=[dict(no="2088", rent=1712, date="Now"), dict(no="3061", rent=1735, date="Now"),
                    dict(no="4012", rent=1748, date="10/1")]),
        dict(name="K", beds=1, baths=1, sf=1072, price_display="per_unit",
             units=[dict(no="2092", rent=1766, date="Now", sf_note="1 sq. ft."),
                    dict(no="4055", rent=1782, date="9/22"), dict(no="4077", rent=1800, date="Now")]),
        dict(name="L", beds=1, baths=1, sf=1092, price_display="contact", units=[]),
        dict(name="P", beds=2, baths=2, sf=1052, price_display="per_unit",
             units=[dict(no="2031", rent=2166, date="Now"), dict(no="3019", rent=2198, date="Now")]),
        dict(name="R", beds=2, baths=2, sf=1339, price_display="per_unit",
             units=[dict(no="4033", rent=2240, date="9/8"), dict(no="4041", rent=2268, date="Now")]),
        dict(name="T", beds=3, baths=2, sf=1393, price_display="contact", units=[]),
        dict(name="U", beds=3, baths=2, sf=1508, price_display="contact", units=[]),
        dict(name="V", beds=4, baths=3, sf=1510, price_display="contact", units=[]),
        dict(name="W", beds=1, baths=1, sf=1339, price_display="contact", units=[],
             in_sf_band=False, live_work=True),
        dict(name="X", beds=0, baths=1, sf=1079, price_display="contact", units=[],
             in_sf_band=False, live_work=True),
        dict(name="Y", beds=1, baths=1, sf=1258, price_display="contact", units=[],
             in_sf_band=False, live_work=True),
    ],
    footer=["Floor tabs — Floor 1: 1 unit · Floor 2: 4 units · Floor 3: 3 units · Floor 4: 6 units",
            "Type filter: Standard Units · Live/Work Units (Office or Business Space!)"],
)

# ---------------------------------- 5. no published price + hard display cap
S["aventerra_dobson_ranch"] = dict(
    community_name="Aventerra at Dobson Ranch", platform="generic",
    trap="The site publishes NO price to a renter anywhere — rents are NULL, not guessed. The unit list HARD-CAPS at 6 rows per plan with no 'show more' and the badge reads 'available units: 5+', so availability is UNGRADED (null), not 6. Also carries the SightMap 'TEMP' placeholder plan (bedroom_count=0, area=1 sf) that must be DROPPED, not surfaced as a real 0-bed group.",
    banners=["Special Offer: Enjoy up to six weeks free on select units. Restrictions apply, see agent for details."],
    plans=[
        dict(name="A1", beds=1, baths=1, sf=680, price_display="quote_only", badge="available units: 5+",
             units=[dict(no=n, date=d) for n, d in [
                 ("1042","Now"),("1108","Now"),("2015","9/3"),("2044","Now"),("3021","9/17"),("3066","Now")]],
             true_count=None),
        dict(name="B1", beds=2, baths=2, sf=860, price_display="quote_only", badge="available units: 5+",
             units=[dict(no=n, date=d) for n, d in [
                 ("1201","Now"),("1233","9/9"),("2210","Now"),("2245","Now"),("3218","10/1"),("3252","Now")]]),
        dict(name="B2", beds=2, baths=2, sf=950, price_display="quote_only", badge="available units: 5+",
             units=[dict(no=n, date=d) for n, d in [
                 ("1305","Now"),("1340","Now"),("2311","9/26"),("2348","Now"),("3319","Now"),("3355","10/7")]]),
        dict(name="TEMP", beds=0, baths=1, sf=1, price_display="per_unit", placeholder=True,
             in_sf_band=False, counts_availability=False, counts_rent=False,
             units=[dict(no="TEMP", rent=1209, date="Now")]),
    ],
    footer=["To view total monthly and move in costs, select a unit and get a quote."],
    gold_overrides=dict(availability_ungraded=True, rents_ungraded=True),
)

# ------------------------- 6. rendered cap vs true count + contact plans IN the band
S["smart_living_cypress_creek"] = dict(
    community_name="Smart Living at Cypress Creek", platform="rentcafe",
    trap="The unit list AND the desktop badge BOTH CAP AT 10. A secondary block carries the UNCAPPED count (Monterey 14, Montecito 12, Cambria 12). Gold uses the uncapped counts. Concession banner does NOT live on the floorplans grid. Three plans read 'Contact for Availability' with no price and no count (Sonoma 2bd/1231, Rutherford 3bd/1230, Napa 3bd/1652): they contribute 0 availability and NO rent, but their SF IS in the band — 2bd 1052-1231, 3bd 1211-1652. Same rule as northbend. (Until 2026-09-18 the source golden labelled these the opposite way and the three plans were deleted from this fixture; resolved in favour of the include band, the labelling guide's written SF-band convention.)",
    banners=["receive ONE MONTH FREE on select 1- and 2-bedroom apartment homes with a 13-month lease"],
    banner_placement="elsewhere",
    plans=[
        dict(name="The Silverado", beds=1, baths=1, sf=631, price_display="per_unit", badge="6 Available",
             units=[dict(no=f"1{n:02d}", rent=1050, date="Now") for n in range(1, 7)]),
        dict(name="The Monterey", beds=1, baths=1, sf=768, price_display="per_unit", badge="10 Available",
             rendered_cap=10, true_count=14,
             units=[dict(no=f"2{n:02d}", rent=1150, date="Now") for n in range(1, 15)]),
        dict(name="The Montecito", beds=2, baths=2, sf=1052, price_display="per_unit", badge="10 Available",
             rendered_cap=10, true_count=12,
             units=[dict(no=f"3{n:02d}", rent=1475, date="Now") for n in range(1, 13)]),
        dict(name="The Cambria", beds=2, baths=2, sf=1113, price_display="per_unit", badge="10 Available",
             rendered_cap=10, true_count=12,
             units=[dict(no=f"4{n:02d}", rent=1575, date="Now") for n in range(1, 13)]),
        dict(name="The Calistoga", beds=3, baths=2, sf=1211, price_display="per_unit", badge="1 Available",
             units=[dict(no="5101", rent=1725, date="Now")]),
        dict(name="The Sonoma", beds=2, baths=2, sf=1231, price_display="contact", units=[]),
        dict(name="The Rutherford", beds=3, baths=2, sf=1230, price_display="contact", units=[]),
        dict(name="The Napa", beds=3, baths=2, sf=1652, price_display="contact", units=[]),
    ],
    footer=["Showing 10 of 14 · The Monterey", "Showing 10 of 12 · The Montecito", "Showing 10 of 12 · The Cambria"],
)

# ---------------------------- 7. base vs total monthly + 'up to N months' -> 12
S["mural_at_stovehouse"] = dict(
    community_name="Mural at Stovehouse", platform="rentcafe",
    trap="The site LEADS with 'Total Monthly Leasing Price' = base + $113.36 of mandatory fees. Gold records BASE rent. Banner 'UP TO THREE MONTHS BASE RENT FREE on select available floor plans' -> 12 weeks (an unspecified 'select' qualifier does NOT null it; a NAMED bed type would). Studio plan 'Satin' is Call for Pricing with no units -> 0 available, but its 562 SF still widens the studio band to 450-562.",
    banners=["Love Where You Live! Contact us today to learn how you can receive UP TO THREE MONTHS BASE RENT FREE on select available floor plans. Plus, if you lease within 72 hours of touring, we will waive your $200 administrative fee. *Limited Time Offer and Subject to Change* *Terms and Conditions Apply*"],
    fee_addon=113.36,
    plans=[
        dict(name="Silk", beds=0, baths=1, sf=450, price_display="per_unit", badge="13 Available",
             units=[dict(no=f"S{n:03d}", rent=979, date=d) for n, d in
                    zip(range(1, 14), ["Now"]*10 + ["8/13", "9/25", "11/1"])]),
        dict(name="Satin", beds=0, baths=1, sf=562, price_display="call_for_pricing", units=[]),
        dict(name="Tweed", beds=1, baths=1, sf=580, price_display="per_unit", badge="9 Available",
             units=[dict(no=f"T{n:03d}", rent=949, date=d) for n, d in
                    zip(range(1, 10), ["Now"]*6 + ["9/17", "9/30", "11/1"])]),
        dict(name="Canvas", beds=1, baths=1, sf=651, price_display="per_unit", badge="12 Available",
             units=[dict(no=f"C{n:03d}", rent=1125, date="Now") for n in range(1, 13)]),
        dict(name="Denim", beds=1, baths=1, sf=720, price_display="per_unit", badge="2 Available",
             units=[dict(no=f"D{n:03d}", rent=1290, date="Now") for n in range(1, 3)]),
        dict(name="Fringe", beds=1, baths=1, sf=790, price_display="per_unit", badge="14 Available",
             units=[dict(no=f"F{n:03d}", rent=1380, date=d) for n, d in
                    zip(range(1, 15), ["Now"]*13 + ["9/30"])]),
        dict(name="Taffeta", beds=1, baths=1, sf=820, price_display="per_unit", badge="1 Available",
             units=[dict(no="TA01", rent=1405, date="Now")]),
        dict(name="Velvet", beds=1, baths=1, sf=835, price_display="per_unit", badge="2 Available",
             units=[dict(no=f"V{n:03d}", rent=1425, date="Now") for n in range(1, 3)]),
        dict(name="Cashmere", beds=1, baths=1, sf=851, price_display="per_unit", badge="3 Available",
             units=[dict(no=f"CA{n:02d}", rent=1450, date="Now") for n in range(1, 4)]),
        dict(name="Linen", beds=2, baths=2, sf=1080, price_display="per_unit", badge="4 Available",
             units=[dict(no=f"L{n:03d}", rent=1699, date="Now") for n in range(1, 5)]),
    ],
    footer=["Studio · 1 Bedroom · 2 Bedrooms — 10 floor plans"],
)

# ------------------------------------- 8. per-unit lease-term RANGE, take LOW
S["the_kelvin"] = dict(
    community_name="The Kelvin", platform="rentcafe",
    trap="Every unit shows a PRICE RANGE (e.g. '$1,000.00 - $1,224.00'). That is RentCafe LEASE-TERM pricing, not base-vs-total: spreads vary per unit and the LOW end always equals the plan card's advertised 'Starting at'. Gold takes the LOW of each unit's range. Banner '1 Month FREE' -> 4 weeks. The '$999' headline is a marketing round-down; the true lowest listed 1BR is $1,000.",
    banners=["Your New Home Starts Here!! Luxury 1 Bedrooms Starting at Just $999! Move Now & Receive 1 Month FREE on Select Apartment Homes! *Offer valid on select apartment homes for a limited time. Restrictions apply."],
    plans=[
        dict(name="A1", beds=1, baths=1, sf=672, price_display="per_unit_range", badge="Starting at $1,000",
             units=[dict(no=f"6{n:03d}", rent=r, rent_high=r + s) for n, r, s in [
                 (205,1000,224),(211,1000,153),(305,1024,190),(311,1038,275),(405,1055,364),
                 (411,1072,201),(505,1090,240)]]),
        dict(name="A2", beds=1, baths=1, sf=763, price_display="per_unit_range", badge="Starting at $1,061",
             units=[dict(no=f"7{n:03d}", rent=r, rent_high=r + s) for n, r, s in [
                 (102,1061,180),(108,1074,255),(202,1088,163),(208,1096,301),(302,1104,215),(308,1112,178)]]),
        dict(name="A3", beds=1, baths=1, sf=755, price_display="per_unit_range", badge="Starting at $1,090",
             units=[dict(no=f"8{n:03d}", rent=r, rent_high=r + s) for n, r, s in [
                 (114,1090,199),(214,1101,264),(314,1118,172),(414,1126,330)]]),
        dict(name="A4", beds=1, baths=1, sf=791, price_display="per_unit_range", badge="Starting at $1,130",
             units=[dict(no=f"9{n:03d}", rent=r, rent_high=r + s) for n, r, s in [
                 (121,1130,205),(221,1141,288),(321,1148,166),(421,1152,243),(521,1154,311)]]),
        dict(name="B1", beds=2, baths=2, sf=1031, price_display="per_unit_range", badge="Starting at $1,260",
             units=[dict(no=f"2{n:03d}", rent=r, rent_high=r + s) for n, r, s in [
                 (106,1260,210),(206,1288,175),(306,1310,262),(406,1335,198),(506,1360,299),(606,1382,221)]]),
        dict(name="B2", beds=2, baths=2, sf=1136, price_display="per_unit_range", badge="Starting at $1,398",
             units=[dict(no=f"3{n:03d}", rent=r, rent_high=r + s) for n, r, s in [
                 (117,1398,188),(217,1420,255),(317,1441,204),(417,1467,276)]]),
        dict(name="C1", beds=3, baths=2, sf=1390, price_display="per_unit_range", badge="Starting at $1,704",
             units=[dict(no="4130", rent=1704, rent_high=1902), dict(no="4230", rent=1734, rent_high=1988)]),
    ],
    footer=["Move-in dates listed range from immediate through 5/7/2027; all listed units count."],
)

# ------------------------- 9. badges undercount + starting-price promo != conc
S["gateway_village_swan_creek"] = dict(
    community_name="Gateway Village at Swan Creek", platform="entrata",
    trap="Plan-card badges UNDERCOUNT the unit tables (Elm's card says '2 Units Available' but lists 3; Sycamore says 'Only 1 Unit Available!' but lists 2) — trust the tables. The site-wide special is a STARTING-PRICE promo ($983 1BR / $1,340 2BR), not weeks/months free, and the top banner is a furnished/short-term-rental notice: NEITHER converts to weeks, so concession_weeks is null. Unit #3219 individually lists 1,320 sf as a corner apartment vs its plan's 1,177 — SF is PLAN-level, so 2BR sf_max stays 1,278.",
    banners=["One Bedrooms Starting At $983 & Two Bedrooms Starting At $1,340. Limited Time Only. Call us for Details!",
             "Furnished Homes & Short-Term Rentals Now Available! Call For Details"],
    plans=[
        dict(name="Birch", beds=1, baths=1, sf=650, price_display="per_unit", badge="3 Units Available",
             units=[dict(no="3112", rent=1039, date="9/19"), dict(no="2412", rent=1039, date="10/02"),
                    dict(no="3412", rent=1039, date="10/03")]),
        dict(name="Holly", beds=1, baths=1, sf=750, price_display="per_unit", badge="1 Unit Available",
             units=[dict(no="2409", rent=1104, date="9/22")]),
        dict(name="Redbud", beds=1, baths=1, sf=840, price_display="per_unit", badge="1 Unit Available",
             units=[dict(no="3206", rent=1199, date="9/12")]),
        dict(name="Sycamore", beds=2, baths=2, sf=1177, price_display="per_unit", badge="Only 1 Unit Available!",
             units=[dict(no="3219", rent=1499, date="Now", sf_note="1,320 sq ft — corner apartment"),
                    dict(no="1411", rent=1499, date="8/07")]),
        dict(name="Elm", beds=2, baths=2, sf=1278, price_display="per_unit", badge="2 Units Available",
             units=[dict(no="3325", rent=1562, date="Now"), dict(no="3425", rent=1562, date="8/07"),
                    dict(no="3225", rent=1587, date="Now")]),
        dict(name="Elder", beds=3, baths=2, sf=1443, price_display="per_unit", badge="3 Units Available",
             units=[dict(no="3122", rent=1724, date="9/02"), dict(no="2401", rent=1749, date="9/19"),
                    dict(no="3300", rent=1774, date="9/22")]),
    ],
    footer=["All units advertise a single 16-month term.",
            "Total Monthly Pricing available via the Calculate My Costs tool (opt-in)."],
)

# ------------------------------- 10. affordable-program bucket out of SF band
S["huntcliff"] = dict(
    community_name="Huntcliff", platform="realpage",
    trap="'Huntcliff Affordable' is an affordable-PROGRAM bucket spanning 674-1,130 sqft, not a floor plan. Folding its 1,130 sf_max into the 1-bedroom band would describe a unit no renter can identify — so it is EXCLUDED from the 1BR SF band (which stays 674-674). No specials anywhere: concession_weeks null.",
    banners=[],
    plans=[
        dict(name="Ascot", beds=1, baths=1, sf=674, price_display="per_unit",
             units=[dict(no="A104", rent=1097, date="Now"), dict(no="A212", rent=1152, date="9/14")]),
        dict(name="Breaker", beds=2, baths=2, sf=906, price_display="per_unit",
             units=[dict(no="B101", rent=1299, date="Now"), dict(no="B205", rent=1304, date="Now"),
                    dict(no="B308", rent=1309, date="10/2")]),
        dict(name="Cambridge", beds=2, baths=2, sf=977, price_display="per_unit",
             units=[dict(no="C110", rent=1468, date="Now"), dict(no="C214", rent=1503, date="9/30")]),
        dict(name="Dexter", beds=3, baths=2, sf=1130, price_display="per_unit",
             units=[dict(no="D102", rent=1984, date="Now"), dict(no="D206", rent=1994, date="Now")]),
        dict(name="Huntcliff Affordable", beds=1, baths=1, sf=674, sf_max_display=1130,
             price_display="call_for_pricing", units=[], in_sf_band=False, affordable=True),
    ],
    footer=["No floorplans found"],
)
