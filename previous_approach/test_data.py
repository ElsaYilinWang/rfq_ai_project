"""
RFQ Test Dataset
=================
Realistic RFQ samples with expected extraction results.
Used to evaluate and improve the extraction module.
"""

test_rfqs = [
    {
        "input": "Siemens motor 5.5kW quantity 3 delivery 6 weeks",
        "expected": {
            "manufacturer": "Siemens",
            "product": "motor",
            "quantity": 3,
            "delivery_time": "6 weeks"
        }
    },
    {
        "input": "Please quote ABB drive ACS580 22kW, need 5 units, 4 week lead time",
        "expected": {
            "manufacturer": "ABB",
            "product": "drive ACS580",
            "quantity": 5,
            "delivery_time": "4 weeks"
        }
    },
    {
        "input": "Need pricing for 10x Schneider contactor LC1D25",
        "expected": {
            "manufacturer": "Schneider",
            "product": "contactor LC1D25",
            "quantity": 10,
            "delivery_time": None
        }
    },
    {
        "input": "Request quotation for Danfoss pressure transmitter MBS3000 qty 2 delivery 8 weeks",
        "expected": {
            "manufacturer": "Danfoss",
            "product": "pressure transmitter MBS3000",
            "quantity": 2,
            "delivery_time": "8 weeks"
        }
    },
    {
        "input": "Hi, can you send quote for twenty Festo pneumatic cylinders DSBC-50-200",
        "expected": {
            "manufacturer": "Festo",
            "product": "pneumatic cylinder DSBC-50-200",
            "quantity": 20,
            "delivery_time": None
        }
    },
    {
        "input": "Urgent: need 1 Fluke 87V multimeter ASAP",
        "expected": {
            "manufacturer": "Fluke",
            "product": "multimeter 87V",
            "quantity": 1,
            "delivery_time": None
        }
    },
    {
        "input": "Looking for Siemens S7-1200 PLC starter kit, quantity seven, 3-4 weeks delivery",
        "expected": {
            "manufacturer": "Siemens",
            "product": "PLC S7-1200 starter kit",
            "quantity": 7,
            "delivery_time": "3-4 weeks"
        }
    },
    {
        "input": "Bearing 6205-2RS quantity 15 delivery 2 weeks",
        "expected": {
            "manufacturer": None,
            "product": "bearing 6205-2RS",
            "quantity": 15,
            "delivery_time": "2 weeks"
        }
    },
    {
        "input": """Hi,

Please quote below item urgently.

Part number: SKF-6205
Qty: 20
Lead time required: ASAP

Thanks""",
        "expected": {
            "manufacturer": "SKF",
            "product": "SKF-6205",
            "quantity": 20,
            "delivery_time": None
        }
    },
    {
        "input": "Item: Pump Seal, MFR: John Crane, Model: 5610, Qty: 5",
        "expected": {
            "manufacturer": "John Crane",
            "product": "pump seal 5610",
            "quantity": 5,
            "delivery_time": None
        }
    },
] 