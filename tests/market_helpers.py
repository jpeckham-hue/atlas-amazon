"""Fake SP-API catalog responses for market-data tests (no network, no credentials).

The shapes follow `searchCatalogItems` (2022-04-01) with
includedData=summaries,attributes,classifications,salesRanks. ASINs starting
B0MKT are synthetic.
"""

from urllib.parse import parse_qs, urlsplit

from atlas_amazon.providers.sp_api import HttpResponse, ScriptedHttpTransport

US = "ATVPDKIKX0DER"
UK = "A1F83G8C2ARO7P"
TS = "2026-10-04T10:00:00+00:00"


def sp_item(asin, title, bullets=(), brand=None, *, marketplace=US, rank=None):
    item = {
        "asin": asin,
        "summaries": [{"marketplaceId": marketplace, "itemName": title}],
        "attributes": {
            "bullet_point": [
                {"value": b, "language_tag": "en_US", "marketplace_id": marketplace}
                for b in bullets
            ]
        },
        "classifications": [
            {
                "marketplaceId": marketplace,
                "classifications": [{"displayName": "Fake Category", "classificationId": "1"}],
            }
        ],
        "salesRanks": [
            {
                "marketplaceId": marketplace,
                "displayGroupRanks": [{"websiteDisplayGroup": "fake", "rank": rank or 1000}],
            }
        ],
    }
    if brand:
        item["summaries"][0]["brand"] = brand
    return item


BOOK = {
    "cozy mystery": [
        sp_item("B0MKTB0001", "The Lighthouse Keeper's Secret: A Small Town Cozy Mystery"),
        sp_item("B0MKTB0002", "Cozy Mystery Box Set: An Amateur Sleuth Series"),
        sp_item("B0BOOK0001", "The Quiet Harbor: A Cozy Mystery"),  # the product itself
        sp_item("B0BOOKC001", "Murder at the Lighthouse"),  # a named competitor
    ],
    "small town mystery": [
        sp_item("B0MKTB0003", "Murder on Main Street: A Small Town Cozy Mystery with Cats"),
        sp_item("B0MKTB0001", "The Lighthouse Keeper's Secret: A Small Town Cozy Mystery"),
        sp_item("B0MKTB0099", "A Village Mystery", marketplace=UK),  # other marketplace only
    ],
}
BOTTLE = {
    "water bottle": [
        sp_item(
            "B0MKTW0001",
            "Summit Insulated Water Bottle with Straw Lid, 32 oz",
            ["Double wall vacuum insulation", "Leak proof straw lid", "BPA free"],
            "Summit",
        ),
        sp_item(
            "B0MKTW0002",
            "River Stainless Steel Water Bottle, Vacuum Insulated",
            ["BPA free", "Leak proof cap", "Wide mouth"],
            "River",
        ),
    ],
    "insulated water bottle": [
        sp_item(
            "B0MKTW0003",
            "Kids Insulated Water Bottle with Straw",
            ["BPA free", "Leak proof", "Double wall vacuum insulation"],
            "Sprout",
        ),
        sp_item(
            "B0MKTW0001",
            "Summit Insulated Water Bottle with Straw Lid, 32 oz",
            ["Double wall vacuum insulation", "Leak proof straw lid", "BPA free"],
            "Summit",
        ),
    ],
}
MARKET = {"book_cozy_mystery": BOOK, "physical_water_bottle": BOTTLE}


def params(request):
    return {k: v[0] for k, v in parse_qs(urlsplit(request.url).query).items()}


def responder(catalog, *, overrides=None):
    """Answer keyword and identifier searches from `catalog` {query: [items]}."""
    overrides = overrides or {}
    by_asin = {i["asin"]: i for items in catalog.values() for i in items}

    def answer(request):
        p = params(request)
        if "keywords" in p:
            query = p["keywords"].replace(",", " ")
            if query in overrides:
                return overrides[query]
            items = catalog.get(query, [])
        else:
            items = [by_asin[a] for a in p["identifiers"].split(",") if a in by_asin]
        return HttpResponse(
            status=200,
            body={"numberOfResults": len(items), "items": items},
            headers={"x-amzn-requestid": "req-fake"},
            retrieved_at=TS,
            transport="scripted",
            synthetic=True,
        )

    return answer


def fake_transport(name_or_catalog, **kwargs):
    catalog = MARKET[name_or_catalog] if isinstance(name_or_catalog, str) else name_or_catalog
    return ScriptedHttpTransport(responder(catalog, **kwargs))


def failure(status, body=None, text=None):
    return HttpResponse(
        status=status, body=body, text=text, retrieved_at=TS, transport="scripted", synthetic=True
    )
