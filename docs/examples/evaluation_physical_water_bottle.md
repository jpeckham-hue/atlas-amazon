> **Synthetic example.** The "model" judgments here are replayed from a scripted recording (`synthetic-scripted-v1`), not from a live model. They exercise the live code path offline. Real agreement figures need a recording made with a live model.

# Judgment evaluation: replayed model vs fixture judgments

Agreement is reported per type; there is no combined score.

| Type | Compared | Agreed | Agreement | Other metrics | Missing | Extra |
|---|---|---|---|---|---|---|
| relevance | 12 | 11 | 92% | mean_absolute_error 0.025 | 0 | 4 |
| intent | 5 | 4 | 80% | mean_absolute_error 0.030 | 0 | 11 |
| entity | 6 | 6 | 100% | blocking_agreement_rate 1.000 | 0 | 13 |
| equivalence | 2 | 2 | 100% | - | 0 | 0 |

Relevance agreement means abs(score difference) <= 0.2.

## relevance disagreements

- **straw lid**: fixture judgments `0.2` vs replayed model `0.5`
  - fixture judgments: The product has no straw lid. (`ev_0df963b1d3731b3fd1226745`)
  - replayed model: Straw lids are a common accessory in this category. (`ev_ab8f4bb6eaa1ce047c71387a`)

## intent disagreements

- **water bottle**: fixture judgments `{'label': 'commercial_investigation', 'score': 0.6}` vs replayed model `{'label': 'transactional', 'score': 0.75}`
  - fixture judgments: Broad browsing query. (`ev_78f884733936d9df04876941`)
  - replayed model: Most shoppers searching this phrase buy within the session. (`ev_20c7c31807080fb3678dac4a`)
