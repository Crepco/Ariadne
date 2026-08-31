### Overall

_Rates carry 95% Wilson score intervals. With samples this small, the interval is the result — a point estimate of 100% from 11 runs is not a 100% success rate._

| Metric | Value |
| --- | --- |
| Runs scored | 26 |
| Correctness | 34.6% [19.4–53.8] |
| Valid-path rate | 7.7% [2.1–24.1] |
| Hallucination rate | 3.8% [0.7–18.9] |
| Optimal of paths found | 100.0% (2 found) |
| Beats BloodHound | 0 of 8 advanced-required |
| Advanced-case recall | 0.0% [0.0–32.4] (0/8) |
| Avg tool calls (solved) | 14.89 |
| Avg runtime (s) | 114.22 |
| Agent misses (of truly reachable) | 11/13 |
| Cost (USD) | $0.2249/run, $5.8473 total |

### Scaling by graph size

| Nodes | Runs | Correctness | Hallucination | Beats BH | Avg tool calls | Avg time (s) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 147 | 26 | 34.6% | 3.8% | 0 | 16.5 | 114.22 |

### By model

| Model | Runs | Correctness (95% CI) | Hallucination | Beats BH | Avg tool calls | Avg time (s) | Avg cost |
| :-- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gemini-flash-lite-latest | 6 | 66.7% [30.0–90.3] | 0.0% | 0 | 25.2 | 124.81 | $0.0000 |
| gpt-4o-mini | 6 | 50.0% [18.8–81.2] | 0.0% | 0 | 6.5 | 14.31 | $0.0031 |
| claude-haiku-4-5 | 6 | 16.7% [3.0–56.4] | 0.0% | 0 | 19.7 | 88.06 | $0.3048 |
| gpt-4o | 6 | 16.7% [3.0–56.4] | 0.0% | 0 | 16.7 | 244.39 | $0.3520 |
| claude-opus-4-8 | 2 | 0.0% [0.0–65.8] | 50.0% | 0 | 10.0 | 70.21 | $0.9439 |

### Failure-mode breakdown by graph size

| Nodes | correct | hallucinated | gave up (path existed) | ran out of steps | wrong path |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 147 | 9 | 1 | 7 | 7 | 2 |
