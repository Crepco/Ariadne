### Overall

| Metric | Value |
| --- | --- |
| Runs | 30 |
| Correctness | 63.3% |
| Valid-path rate | 63.3% |
| Hallucination rate | 20.0% |
| Optimal of paths found | 100.0% (19 found) |
| Beats BloodHound | 3 of 9 advanced-required |
| Advanced-case recall | 33.3% (3/9) |
| Avg tool calls (solved) | 3.58 |
| Avg runtime (s) | 20.79 |
| Agent misses (of truly reachable) | 11/30 |
| Cost (USD) | $0.0015/run, $0.0444 total |

### Scaling by graph size

| Nodes | Runs | Correctness | Hallucination | Beats BH | Avg tool calls | Avg time (s) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 216 | 10 | 60.0% | 10.0% | 1 | 5.3 | 18.60 |
| 481 | 10 | 70.0% | 30.0% | 1 | 5.2 | 19.65 |
| 813 | 10 | 60.0% | 20.0% | 1 | 7.1 | 24.12 |

### Failure-mode breakdown by graph size

| Nodes | correct | hallucinated | gave up (path existed) | ran out of steps | wrong path |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 216 | 6 | 1 | 3 | 0 | 0 |
| 481 | 7 | 3 | 0 | 0 | 0 |
| 813 | 6 | 2 | 2 | 0 | 0 |
