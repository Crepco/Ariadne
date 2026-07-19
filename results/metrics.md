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
| Avg runtime (s) | 18.62 |
| Agent misses (of truly reachable) | 11/30 |
| Cost (USD) | $0.0013/run, $0.0390 total |

### Scaling by graph size

| Nodes | Runs | Correctness | Hallucination | Beats BH | Avg tool calls | Avg time (s) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 216 | 10 | 60.0% | 20.0% | 1 | 5.3 | 18.31 |
| 481 | 10 | 70.0% | 20.0% | 1 | 4.8 | 17.17 |
| 813 | 10 | 60.0% | 20.0% | 1 | 6.1 | 20.38 |

### Failure-mode breakdown by graph size

| Nodes | correct | hallucinated | gave up (path existed) | ran out of steps | wrong path |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 216 | 6 | 2 | 2 | 0 | 0 |
| 481 | 7 | 2 | 1 | 0 | 0 |
| 813 | 6 | 2 | 2 | 0 | 0 |
