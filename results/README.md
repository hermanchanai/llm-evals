# Results

| file | what it is |
|---|---|
| `recorded/2026-09-18_luna-vs-haiku.jsonl` | every reply from the 2026-09-18 run: GPT-5.6 Luna and Claude Haiku 4.5, both tasks, 3 repetitions (450 rows) |
| `recorded/2026-10-18_permits-three-models.jsonl` | Task B replies from a 2026-10-18 run: Haiku 4.5, Haiku 5.5 and GPT-6 Luna, 3 repetitions (585 rows) |
| `2026-09-18_luna-vs-haiku.md` | report regenerated from the first recording |
| `2026-10-18_permits-three-models.md` | report regenerated from the second recording |

Each recorded row holds the raw reply text, the token usage the provider returned, latency,
finish status and the cost computed at run time. Regenerate a report with:

```bash
python -m llm_evals.replay results/recorded/2026-09-18_luna-vs-haiku.jsonl --out results/2026-09-18_luna-vs-haiku.md
```

A test fails if the regenerated file differs from the committed one, or if any recomputed
cost differs from the run-time cost by more than $0.000001.

Notes on the runs:

- Both are on-demand, standard tier, no retries, temperature 0 (Haiku 5.5: thinking disabled).
  A batch API would roughly halve the Anthropic costs; that path was not measured here.
- On 2026-09-18, Luna's provider cached about 33k of its 48k rent input tokens automatically;
  Haiku was sent no cache controls. Part of the rent cost gap is that difference.
- The 2026-09-18 Haiku replies wrapped every rent answer in a code fence. The scorer accepts
  one wrapping fence, as the production extractor does; a stricter parser scored them 0/30.
- The 2026-10-18 run sent the same system prompt and user message as `llm_evals.run`. Its
  original scorer parsed replies through the production classifier; the strict scorer here
  gives the same correct counts (162, 150, 160).
