# paper/

The short write-up. Target: a proof-of-concept / short paper — LaTeX (IEEE template) or Markdown depending on the venue.

## Structure

1. **Problem** — AD attack paths; BloodHound is rule-based and misses unusual-shaped chains that a human still has to reason through.
2. **Method** — synthetic BloodHound-schema graphs in Neo4j; a ReAct LLM agent with 4 graph-query tools; Cypher shortest paths as ground truth.
3. **Results** — the metrics table + scaling plots (pull from [`../results/`](../results/)).
4. **Limitations** — synthetic-only data; single/few models; random graph structure.
5. **Ethics** — fully synthetic, local data; no live network.

## Handling the "why synthetic data?" reviewer question

Address it head-on and it's a non-issue:

- Synthetic AD graphs conform to the **BloodHound schema** — the same structure real collections use — which lets us control size and **guarantee ground truth**.
- Synthetic evaluation is **standard practice** for reproducible benchmarks (removes org-specific noise and privacy concerns).
- List **validation on live-collected AD data as future work** — readily accepted for a proof-of-concept.

## To add

- `main.tex` / `main.md` + bibliography.
- Figures/tables `\input`-ed or linked from `../results/` so the paper stays in sync.
- A reproducibility appendix pointing at the code + logs artifact.
