# retrieval/corpus.py

"""
Mock historical corpus for Phase 14 semantic retrieval — 11 records,
mock/sanitized, using brands already established elsewhere in this
project (analyzer_cases.json, test_data.py) rather than inventing new
ones.

Deliberately NOT just 11 unrelated items. Three pairs are near-
duplicates by design, because a corpus where everything is easily
distinguishable can't actually demonstrate discrimination — it would
"work" even if similarity search were replaced with a coin flip:

  - Records 1 and 11: same product type (miniature circuit breaker,
    DIN rail) from two different manufacturers (ABB vs. Schneider
    Electric). Tests whether manufacturer-specific query language
    steers to the right supplier rather than any circuit breaker.
  - Records 5 and 6: same product type (mechanical seal for a
    centrifugal pump) from two different manufacturers (John Crane
    vs. Flowserve). Same test, different product family.
  - Records 1 and 10: same manufacturer (ABB) but different product
    types (circuit breaker vs. VFD drive). Tests that shared brand
    doesn't cause a false-positive match on the wrong product.
"""

from retrieval.schemas import HistoricalItem

HISTORICAL_ITEMS = [
    HistoricalItem(
        description="ABB miniature circuit breaker 10A, DIN rail mounted",
        supplier_name="Mock ABB Supplier",
        manufacturer="ABB",
    ),
    HistoricalItem(
        description="Schneider Electric contactor LC1D25, 25A, 24V coil",
        supplier_name="Mock Schneider Supplier",
        manufacturer="Schneider Electric",
    ),
    HistoricalItem(
        description="Siemens S7-1200 PLC starter kit with power supply",
        supplier_name="Mock Siemens Supplier",
        manufacturer="Siemens",
    ),
    HistoricalItem(
        description="SKF deep groove ball bearing 6205-2RS, sealed",
        supplier_name="Mock SKF Supplier",
        manufacturer="SKF",
    ),
    HistoricalItem(
        description="John Crane mechanical seal for centrifugal pump, high temperature service",
        supplier_name="Mock John Crane Supplier",
        manufacturer="John Crane",
    ),
    HistoricalItem(
        description="Flowserve mechanical seal kit for centrifugal pump, standard duty",
        supplier_name="Mock Flowserve Supplier",
        manufacturer="Flowserve",
    ),
    HistoricalItem(
        description="Danfoss pressure transmitter MBS3000, 0-16 bar range",
        supplier_name="Mock Danfoss Supplier",
        manufacturer="Danfoss",
    ),
    HistoricalItem(
        description="Festo pneumatic cylinder DSBC-50-200, double acting",
        supplier_name="Mock Festo Supplier",
        manufacturer="Festo",
    ),
    HistoricalItem(
        description="Fluke 87V digital multimeter, true RMS",
        supplier_name="Mock Fluke Supplier",
        manufacturer="Fluke",
    ),
    HistoricalItem(
        description="ABB VFD drive ACS580, 22kW, IP20 enclosure",
        supplier_name="Mock ABB Supplier",
        manufacturer="ABB",
    ),
    HistoricalItem(
        description="Schneider Electric miniature circuit breaker, 16A, DIN rail",
        supplier_name="Mock Schneider Supplier",
        manufacturer="Schneider Electric",
    ),
]
