# Evaluation: replay of 2026-09-18_luna-vs-haiku.jsonl

Planned repetitions per model: 3 (no RNG seed supplied)

## rent

| model | attempted | valid complete | correct records | field accuracy | hallucinations | misses | strict / attempted | known $ total | unknown costs | $/1k attempted | $/1k correct | p50 ms | p95 ms | repetition strict spread |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| anthropic:claude-haiku-4-5 | 30 | 30 | 18 | 95.1% | 15 | 3 | 60.0% | $0.0911 | 0 | $3.0383 | $5.0638 | 1713 | 2328 | 60.0%-60.0% |
| openai:gpt-5.6-luna | 30 | 30 | 18 | 94.4% | 9 | 16 | 60.0% | $0.0087 | 0 | $0.2905 | $0.4841 | 1268 | 1791 | 50.0%-70.0% |

### Errors and disagreements (first repetition)

- **anthropic:claude-haiku-4-5** `aventerra_dobson_ranch`: beds=1 available: gold=None got=6 [hallucination]; beds=2 available: gold=None got=11 [hallucination]
- **anthropic:claude-haiku-4-5** `huntcliff`: beds=2 available: gold=5 got=4 [field_drift]
- **anthropic:claude-haiku-4-5** `smart_living_cypress_creek`: beds=1 available: gold=20 got=14 [field_drift]; beds=2 available: gold=24 got=12 [field_drift]; beds=3 rent_max: gold=1725 got=None [miss]
- **anthropic:claude-haiku-4-5** `union_landing`: beds=1 available: gold=None got=0 [hallucination]; beds=2 available: gold=None got=0 [hallucination]; beds=3 available: gold=None got=0 [hallucination]
- **openai:gpt-5.6-luna** `aventerra_dobson_ranch`: beds=1 available: gold=None got=6 [hallucination]; beds=2 available: gold=None got=12 [hallucination]
- **openai:gpt-5.6-luna** `northbend`: beds=0 rent_max: gold=1422 got=None [miss]; beds=1 rent_max: gold=1800 got=None [miss]; beds=1 available: gold=8 got=9 [field_drift]; beds=2 rent_max: gold=2268 got=None [miss]
- **openai:gpt-5.6-luna** `smart_living_cypress_creek`: beds=2 available: gold=24 got=22 [field_drift]
- **openai:gpt-5.6-luna** `the_kelvin`: beds=1 rent_max: gold=1154 got=None [miss]; beds=2 rent_max: gold=1467 got=None [miss]; beds=3 rent_max: gold=1734 got=None [miss]
- **openai:gpt-5.6-luna** `union_landing`: beds=1 rent_min: gold=1216 got=None [miss]; beds=2 rent_min: gold=1453 got=None [miss]; beds=3 rent_min: gold=1673 got=None [miss]

## permits

| model | attempted | valid complete | correct records | field accuracy | hallucinations | misses | strict / attempted | known $ total | unknown costs | $/1k attempted | $/1k correct | p50 ms | p95 ms | repetition strict spread |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| anthropic:claude-haiku-4-5 | 195 | 195 | 166 | 85.1% | 0 | 0 | 85.1% | $0.1335 | 0 | $0.6846 | $0.8042 | 523 | 800 | 84.6%-86.2% |
| openai:gpt-5.6-luna | 195 | 195 | 159 | 81.5% | 0 | 0 | 81.5% | $0.0236 | 0 | $0.1210 | $0.1485 | 679 | 877 | 81.5%-81.5% |

### Errors and disagreements (first repetition)

- **anthropic:claude-haiku-4-5** `8884`: single_family -> commercial
- **anthropic:claude-haiku-4-5** `10602`: townhome -> single_family
- **anthropic:claude-haiku-4-5** `12836`: multifamily -> commercial
- **anthropic:claude-haiku-4-5** `13750`: townhome -> multifamily
- **anthropic:claude-haiku-4-5** `12040`: single_family -> multifamily
- **anthropic:claude-haiku-4-5** `11512`: single_family -> multifamily
- **anthropic:claude-haiku-4-5** `10015`: single_family -> multifamily
- **anthropic:claude-haiku-4-5** `9639`: multifamily -> mixed
- **anthropic:claude-haiku-4-5** `11422`: mixed -> unknown
- **openai:gpt-5.6-luna** `8884`: single_family -> commercial
- **openai:gpt-5.6-luna** `10602`: townhome -> single_family
- **openai:gpt-5.6-luna** `13046`: single_family -> unknown
- **openai:gpt-5.6-luna** `12836`: multifamily -> unknown
- **openai:gpt-5.6-luna** `13750`: townhome -> multifamily
- **openai:gpt-5.6-luna** `12040`: single_family -> multifamily
- **openai:gpt-5.6-luna** `11512`: single_family -> multifamily
- **openai:gpt-5.6-luna** `10015`: single_family -> multifamily
- **openai:gpt-5.6-luna** `10775`: townhome -> multifamily
- **openai:gpt-5.6-luna** `12097`: mixed -> commercial
- **openai:gpt-5.6-luna** `13790`: mixed -> commercial
- **openai:gpt-5.6-luna** `11422`: mixed -> unknown

All attempted calls enter strict success, including API, parse, schema, refusal and truncation failures.
Known costs include failed outputs. Unknown charges remain reserved; cost rankings are withheld when any cost is unknown.
Hallucinations are incorrect fields and also shown separately. Rent field accuracy weights fields; strict success weights records.
Repetition ranges are descriptive; overlapping ranges do not prove model equivalence.

## Rent: strict passes per case, all repetitions (hallucinated / missed fields)

| case | anthropic:claude-haiku-4-5 | openai:gpt-5.6-luna |
|---|---|---|
| avail_sandy_springs | 3/3 (h0/m0) | 3/3 (h0/m0) |
| aventerra_dobson_ranch | 0/3 (h6/m0) | 0/3 (h6/m0) |
| emblem_conyers | 3/3 (h0/m0) | 3/3 (h0/m0) |
| gateway_village_swan_creek | 3/3 (h0/m0) | 3/3 (h0/m0) |
| huntcliff | 0/3 (h0/m0) | 3/3 (h0/m0) |
| mural_at_stovehouse | 3/3 (h0/m0) | 3/3 (h0/m0) |
| northbend | 3/3 (h0/m0) | 2/3 (h0/m3) |
| smart_living_cypress_creek | 0/3 (h0/m3) | 0/3 (h0/m1) |
| the_kelvin | 3/3 (h0/m0) | 1/3 (h0/m3) |
| union_landing | 0/3 (h9/m0) | 0/3 (h3/m9) |

## Permits: correct by gold class, all repetitions

| gold class | anthropic:claude-haiku-4-5 | openai:gpt-5.6-luna |
|---|---|---|
| commercial | 54/54 | 54/54 |
| mixed | 9/12 | 2/12 |
| multifamily | 30/36 | 33/36 |
| single_family | 36/48 | 34/48 |
| townhome | 24/30 | 21/30 |
| unknown | 13/15 | 15/15 |

## Permits: majority answer per case across repetitions, where any model missed

| row_id | gold | anthropic:claude-haiku-4-5 | openai:gpt-5.6-luna |
|---|---|---|---|
| 8884 | single_family | **commercial** | **commercial** |
| 9322 | unknown | **commercial** | unknown |
| 9639 | multifamily | **mixed** | multifamily |
| 10015 | single_family | **multifamily** | **multifamily** |
| 10602 | townhome | **single_family** | **single_family** |
| 10775 | townhome | townhome | **multifamily** |
| 11422 | mixed | **unknown** | **unknown** |
| 11512 | single_family | **multifamily** | **multifamily** |
| 12040 | single_family | **multifamily** | single_family |
| 12097 | mixed | mixed | **commercial** |
| 12836 | multifamily | **commercial** | **unknown** |
| 13046 | single_family | single_family | **unknown** |
| 13750 | townhome | **multifamily** | **multifamily** |
| 13790 | mixed | mixed | **commercial** |

Costs are recomputed from the recorded token usage with llm_evals/pricing.py; 0 of 450 rows differ from the cost recorded at run time by more than $0.000001.
