### Overall

_Rates carry 95% Wilson score intervals. With samples this small, the interval is the result — a point estimate of 100% from 11 runs is not a 100% success rate._

| Metric | Value |
| --- | --- |
| Runs scored | 39 |
| Correctness | 89.7% [76.4–95.9] |
| Valid-path rate | 89.7% [76.4–95.9] |
| Hallucination rate | 0.0% [0.0–9.0] |
| Optimal of paths found | 97.1% (35 found) |
| Beats BloodHound | 12 of 12 advanced-required |
| Advanced-case recall | 100.0% [75.7–100.0] (12/12) |
| Avg tool calls (solved) | 5.69 |
| Avg runtime (s) | 34.67 |
| Agent misses (of truly reachable) | 3/38 |
| Cost (USD) | $0.0000/run, $0.0000 total |

### Scaling by graph size

| Nodes | Runs | Correctness | Hallucination | Beats BH | Avg tool calls | Avg time (s) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 222 | 13 | 92.3% | 0.0% | 4 | 7.2 | 34.66 |
| 487 | 13 | 100.0% | 0.0% | 4 | 6.0 | 30.52 |
| 819 | 13 | 76.9% | 0.0% | 4 | 8.1 | 38.84 |

### Failure-mode breakdown by graph size

| Nodes | correct | hallucinated | gave up (path existed) | ran out of steps | wrong path |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 222 | 12 | 0 | 0 | 1 | 0 |
| 487 | 13 | 0 | 0 | 0 | 0 |
| 819 | 10 | 0 | 0 | 3 | 0 |
