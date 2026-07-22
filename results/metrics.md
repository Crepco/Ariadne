### Overall

| Metric | Value |
| --- | --- |
| Runs | 37 |
| Correctness | 83.8% |
| Valid-path rate | 81.1% |
| Hallucination rate | 0.0% |
| Optimal of paths found | 100.0% (30 found) |
| Beats BloodHound | 10 of 12 advanced-required |
| Advanced-case recall | 83.3% (10/12) |
| Avg tool calls (solved) | 5.13 |
| Avg runtime (s) | 24.87 |
| Agent misses (of truly reachable) | 6/36 |
| Cost (USD) | $0.0104/run, $0.3838 total |

### Scaling by graph size

| Nodes | Runs | Correctness | Hallucination | Beats BH | Avg tool calls | Avg time (s) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 222 | 24 | 87.5% | 0.0% | 7 | 6.1 | 21.47 |
| 487 | 13 | 76.9% | 0.0% | 3 | 6.4 | 31.16 |

### By model

| Model | Runs | Correctness | Hallucination | Beats BH | Avg tool calls | Avg time (s) | Avg cost |
| :-- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| openai/gpt-4o | 11 | 100.0% | 0.0% | 4 | 5.2 | 16.81 | $0.0306 |
| openai/gpt-4o-mini | 26 | 76.9% | 0.0% | 6 | 6.7 | 28.28 | $0.0018 |

### Failure-mode breakdown by graph size

| Nodes | correct | hallucinated | gave up (path existed) | ran out of steps | wrong path |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 222 | 21 | 0 | 3 | 0 | 0 |
| 487 | 10 | 0 | 3 | 0 | 0 |
