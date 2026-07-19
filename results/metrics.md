### Overall

| Metric | Value |
| --- | --- |
| Runs | 27 |
| Correctness | 70.4% |
| Valid-path rate | 70.4% |
| Hallucination rate | 29.6% |
| Optimal of paths found | 100.0% (19 found) |
| Beats BloodHound | 3 of 5 advanced-required |
| Avg tool calls (solved) | 3.53 |
| Avg runtime (s) | 17.73 |
| Agent misses (of truly reachable) | 6/25 |
| Cost (USD) | $0.0011/run, $0.0284 total |

### Scaling by graph size

| Nodes | Runs | Correctness | Hallucination | Beats BH | Avg tool calls | Avg time (s) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 213 | 9 | 66.7% | 33.3% | 1 | 5.0 | 19.84 |
| 478 | 9 | 66.7% | 33.3% | 1 | 4.7 | 17.55 |
| 810 | 9 | 77.8% | 22.2% | 1 | 4.2 | 15.80 |

### Failure-mode breakdown by graph size

| Nodes | correct | hallucinated | gave up (path existed) | ran out of steps | wrong path |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 213 | 6 | 3 | 0 | 0 | 0 |
| 478 | 6 | 3 | 0 | 0 | 0 |
| 810 | 7 | 2 | 0 | 0 | 0 |
