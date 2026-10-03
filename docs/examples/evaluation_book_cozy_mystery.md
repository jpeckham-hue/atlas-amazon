> **Synthetic example.** The "model" judgments here are replayed from a scripted recording (`synthetic-scripted-v1`), not from a live model. They exercise the live code path offline. Real agreement figures need a recording made with a live model.

# Judgment evaluation: replayed model vs fixture judgments

Agreement is reported per type; there is no combined score.

| Type | Compared | Agreed | Agreement | Other metrics | Missing | Extra |
|---|---|---|---|---|---|---|
| relevance | 13 | 12 | 92% | mean_absolute_error 0.027 | 0 | 0 |
| intent | 4 | 3 | 75% | mean_absolute_error 0.025 | 0 | 9 |
| entity | 3 | 3 | 100% | blocking_agreement_rate 1.000 | 0 | 10 |
| equivalence | 1 | 1 | 100% | - | 0 | 0 |

Relevance agreement means abs(score difference) <= 0.2.

## relevance disagreements

- **small town**: fixture judgments `0.3` vs replayed model `0.65`
  - fixture judgments: A setting word; on its own not a book search. (`ev_2c5d1441b8308bf4825ef221`)
  - replayed model: A small-town setting is a core cozy-mystery convention. (`ev_87b99c08ab37dfee6b005f8a`)

## intent disagreements

- **cozy mystery**: fixture judgments `{'label': 'commercial_investigation', 'score': 0.7}` vs replayed model `{'label': 'transactional', 'score': 0.8}`
  - fixture judgments: Genre browsing. (`ev_8b676afc6e54ac3e2de275fa`)
  - replayed model: Genre queries on Amazon usually precede a purchase. (`ev_62913a83c66d4f61a7c4a193`)
