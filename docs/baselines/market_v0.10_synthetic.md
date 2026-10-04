# Market data comparison (v0.10, synthetic)

> **SYNTHETIC, not live.** Fake SP-API `searchCatalogItems` responses (`tests/market_helpers.py`, ASINs `B0MKT…`) fed through the real adapter and research run, to show what the live comparison reports. No network calls were made. Catalog evidence only: no search volume, conversion or ad data.

### book_cozy_mystery

- Market queries (sp-api-catalog): `cozy mystery`, `small town mystery`; 3 catalog items kept as competitor listings.
- New candidate keywords: `town cozy`, `small town cozy`, `town cozy mystery`, `mystery with cats`.
- New candidates with no demand data (stay unscored on demand): `town cozy`, `small town cozy`, `town cozy mystery`, `mystery with cats`.
- Fixture candidates confirmed by market listings: `amateur sleuth` (1/3), `cozy mystery` (3/3), `cozy mystery with cats` (1/3), `small town` (2/3).
- Fixture candidates absent from market listings: `agatha christie cozy mystery`, `cozy mystery books`, `cozy mystery kindle unlimited`, `cozy mystery series`, `harbor town`, `mystery books`, `mystery books cozy`, `small town murder mystery`, `small town mystery`, `small town mystery books`.
- Recommendations added: none; removed: none.

Ranking unchanged.

| Unsupported keyword | Unsupported terms | Market listings | Recommended | Packed |
|---|---|---|---|---|
| cozy mystery with cats | cat | 1 | no | no |

### physical_water_bottle

- Market queries (sp-api-catalog): `water bottle`, `insulated water bottle`; 3 catalog items kept as competitor listings.
- New candidate keywords: `lid 32`, `32 oz`, `bottle with straw`, `straw lid 32`, `lid 32 oz`, `proof straw`, `leak proof straw`, `proof straw lid`, `steel water`, `bottle vacuum`, `vacuum insulated`, `stainless steel water`, `steel water bottle`, `water bottle vacuum`, `bottle vacuum insulated`, `proof cap`, `leak proof cap`.
- New candidates with no demand data (stay unscored on demand): `lid 32`, `32 oz`, `bottle with straw`, `straw lid 32`, `lid 32 oz`, `proof straw`, `leak proof straw`, `proof straw lid`, `steel water`, `bottle vacuum`, `vacuum insulated`, `stainless steel water`, `steel water bottle`, `water bottle vacuum`, `bottle vacuum insulated`, `proof cap`, `leak proof cap`.
- Fixture candidates confirmed by market listings: `bpa free` (3/3), `double wall` (2/3), `double wall vacuum` (2/3), `insulated water` (2/3), `insulated water bottle` (2/3), `insulated water bottle with straw` (2/3), `leak proof` (3/3), `stainless steel` (1/3), `straw lid` (1/3), `vacuum insulation` (2/3), `wall vacuum` (2/3), `wall vacuum insulation` (2/3), `water bottle` (3/3), `water bottle with straw` (2/3).
- Fixture candidates absent from market listings: `bottle water`, `hydra water bottle`, `insulated water bottle stainless steel`, `kids water bottle`, `water bottle 32 oz`, `water bottle insulated`, `water bottles for kids`.
- Recommendations added: none; removed: none.

| Keyword | Rank before | Rank after |
|---|---|---|
| water bottle with straw | 10 | 8 |
| stainless steel | 8 | 9 |
| water bottles for kids | 9 | 10 |
| hydra water bottle | 12 | 11 |
| straw lid | 11 | 12 |
| bpa free | 15 | 14 |
| vacuum insulation | 14 | 15 |

| Unsupported keyword | Unsupported terms | Market listings | Recommended | Packed |
|---|---|---|---|---|
| insulated water bottle with straw | straw | 2 | no | no |
| water bottle with straw | straw | 2 | no | no |
| water bottles for kids | kid | 0 | no | no |
| straw lid | straw | 1 | no | no |
| bpa free | bpa, free | 3 | no | no |
