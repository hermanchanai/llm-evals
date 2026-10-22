# Evaluation: replay of 2026-10-18_permits-three-models.jsonl

Planned repetitions per model: 3 (no RNG seed supplied)

## permits

| model | attempted | valid complete | correct records | field accuracy | hallucinations | misses | strict / attempted | known $ total | unknown costs | $/1k attempted | $/1k correct | p50 ms | p95 ms | repetition strict spread |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| anthropic:claude-haiku-4-5 | 195 | 195 | 162 | 83.1% | 0 | 0 | 83.1% | $0.1335 | 0 | $0.6846 | $0.8241 | 554 | 653 | 83.1%-83.1% |
| anthropic:claude-haiku-5-5 | 195 | 194 | 150 | 76.9% | 0 | 0 | 76.9% | $0.0186 | 0 | $0.0954 | $0.1240 | 739 | 1677 | 75.4%-78.5% |
| openai:gpt-6-luna | 195 | 195 | 160 | 82.1% | 0 | 0 | 82.1% | $0.0117 | 0 | $0.0600 | $0.0732 | 786 | 992 | 81.5%-83.1% |

### Errors and disagreements (first repetition)

- **anthropic:claude-haiku-4-5** `8884`: single_family -> commercial
- **anthropic:claude-haiku-4-5** `10602`: townhome -> single_family
- **anthropic:claude-haiku-4-5** `12836`: multifamily -> single_family
- **anthropic:claude-haiku-4-5** `13750`: townhome -> multifamily
- **anthropic:claude-haiku-4-5** `11823`: multifamily -> commercial
- **anthropic:claude-haiku-4-5** `11512`: single_family -> multifamily
- **anthropic:claude-haiku-4-5** `10015`: single_family -> multifamily
- **anthropic:claude-haiku-4-5** `9639`: multifamily -> mixed
- **anthropic:claude-haiku-4-5** `13790`: mixed -> commercial
- **anthropic:claude-haiku-4-5** `11422`: mixed -> unknown
- **anthropic:claude-haiku-4-5** `9322`: unknown -> commercial
- **anthropic:claude-haiku-5-5** `8884`: single_family -> unknown
- **anthropic:claude-haiku-5-5** `12553`: single_family -> unknown
- **anthropic:claude-haiku-5-5** `9327`: single_family -> commercial
- **anthropic:claude-haiku-5-5** `10602`: townhome -> single_family
- **anthropic:claude-haiku-5-5** `12836`: multifamily -> commercial
- **anthropic:claude-haiku-5-5** `10666`: single_family -> commercial
- **anthropic:claude-haiku-5-5** `13750`: townhome -> multifamily
- **anthropic:claude-haiku-5-5** `12040`: single_family -> multifamily
- **anthropic:claude-haiku-5-5** `11512`: single_family -> multifamily
- **anthropic:claude-haiku-5-5** `10015`: single_family -> multifamily
- **anthropic:claude-haiku-5-5** `11754`: unknown -> commercial
- **anthropic:claude-haiku-5-5** `9153`: unknown -> commercial
- **anthropic:claude-haiku-5-5** `11422`: mixed -> unknown
- **anthropic:claude-haiku-5-5** `11950`: unknown -> commercial
- **anthropic:claude-haiku-5-5** `9322`: unknown -> commercial
- **openai:gpt-6-luna** `8884`: single_family -> unknown
- **openai:gpt-6-luna** `9327`: single_family -> commercial
- **openai:gpt-6-luna** `10602`: townhome -> single_family
- **openai:gpt-6-luna** `13046`: single_family -> unknown
- **openai:gpt-6-luna** `12836`: multifamily -> commercial
- **openai:gpt-6-luna** `13750`: townhome -> multifamily
- **openai:gpt-6-luna** `11512`: single_family -> multifamily
- **openai:gpt-6-luna** `10015`: single_family -> multifamily
- **openai:gpt-6-luna** `10775`: townhome -> multifamily
- **openai:gpt-6-luna** `12097`: mixed -> commercial
- **openai:gpt-6-luna** `13790`: mixed -> commercial
- **openai:gpt-6-luna** `11422`: mixed -> unknown

All attempted calls enter strict success, including API, parse, schema, refusal and truncation failures.
Known costs include failed outputs. Unknown charges remain reserved; cost rankings are withheld when any cost is unknown.
Hallucinations are incorrect fields and also shown separately. Rent field accuracy weights fields; strict success weights records.
Repetition ranges are descriptive; overlapping ranges do not prove model equivalence.

## Permits: correct by gold class, all repetitions

| gold class | anthropic:claude-haiku-4-5 | anthropic:claude-haiku-5-5 | openai:gpt-6-luna |
|---|---|---|---|
| commercial | 54/54 | 54/54 | 54/54 |
| mixed | 6/12 | 9/12 | 4/12 |
| multifamily | 27/36 | 33/36 | 33/36 |
| single_family | 39/48 | 27/48 | 33/48 |
| townhome | 24/30 | 23/30 | 21/30 |
| unknown | 12/15 | 4/15 | 15/15 |

## Permits: majority answer per case across repetitions, where any model missed

| row_id | gold | anthropic:claude-haiku-4-5 | anthropic:claude-haiku-5-5 | openai:gpt-6-luna |
|---|---|---|---|---|
| 8884 | single_family | **commercial** | **commercial** | **commercial** |
| 9153 | unknown | unknown | **commercial** | unknown |
| 9322 | unknown | **commercial** | **commercial** | unknown |
| 9327 | single_family | single_family | **commercial** | **commercial** |
| 9639 | multifamily | **mixed** | multifamily | multifamily |
| 10015 | single_family | **multifamily** | **multifamily** | **multifamily** |
| 10602 | townhome | **single_family** | **single_family** | **single_family** |
| 10666 | single_family | single_family | **commercial** | single_family |
| 10775 | townhome | townhome | townhome | **multifamily** |
| 11422 | mixed | **unknown** | **unknown** | **unknown** |
| 11512 | single_family | **multifamily** | **multifamily** | **multifamily** |
| 11754 | unknown | unknown | **commercial** | unknown |
| 11823 | multifamily | **commercial** | multifamily | multifamily |
| 11950 | unknown | unknown | **commercial** | unknown |
| 12040 | single_family | single_family | **multifamily** | single_family |
| 12097 | mixed | mixed | mixed | **commercial** |
| 12553 | single_family | single_family | **unknown** | single_family |
| 12836 | multifamily | **single_family** | **commercial** | **unknown** |
| 13046 | single_family | single_family | single_family | **unknown** |
| 13750 | townhome | **multifamily** | **multifamily** | **multifamily** |
| 13790 | mixed | **commercial** | mixed | **commercial** |

Costs are recomputed from the recorded token usage with llm_evals/pricing.py; 0 of 585 rows differ from the cost recorded at run time by more than $0.000001.
