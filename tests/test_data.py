"""
RFQ Parser Test Dataset
========================
Contains real data test cases from RFQ 6000186510
and synthetic edge cases to test flag logic.
"""

# ---------------------------------------------------------------
# Real data test cases — from RFQ 6000186510
# ---------------------------------------------------------------

real_test_cases = [
    {
        "description": "HPS Lamp — two sourcing identifiers",
        "input": {
            "material_number": "1000163281",
            "long_description": "LAMP,HIGH INTENSITY DISCHARGE;HPS,400 W",
            "uom": "each",
            "quantity": 22,
            "pn_model_mfr": " LU400/H/ECO - GE LIGHTING\n 281179 - OSRAM",
            "lead_time_str": "28/05/2026\n11 Weeks"
        },
        "expected": {
            "material_number": "1000163281",
            "uom": "each",
            "quantity": 22,
            "lead_time_date": "28/05/2026",
            "lead_time_weeks": 11,
            "sourcing_identifiers": [
                {"part_number": "LU400/H/ECO", "manufacturer": "GE LIGHTING"},
                {"part_number": "281179", "manufacturer": "OSRAM"}
            ],
            "flags": []
        }
    },
    {
        "description": "Combustion Air Blower Cord — single identifier",
        "input": {
            "material_number": "1000205061",
            "long_description": "CORD;EXTN,COMBUSTION AIR BLOWER",
            "uom": "each",
            "quantity": 5,
            "pn_model_mfr": " 612979 - FIMA MASCHINENBAU GMBH",
            "lead_time_str": "05/06/2026\n12 Weeks"
        },
        "expected": {
            "material_number": "1000205061",
            "uom": "each",
            "quantity": 5,
            "lead_time_date": "05/06/2026",
            "lead_time_weeks": 12,
            "sourcing_identifiers": [
                {"part_number": "612979",
                 "manufacturer": "FIMA MASCHINENBAU GMBH"}
            ],
            "flags": []
        }
    },
    {
        "description": "Bevel Gear — hyphenated part number",
        "input": {
            "material_number": "1000148955",
            "long_description": "GEAR,BEVEL: SET WITH PINION SHAFT",
            "uom": "each",
            "quantity": 2,
            "pn_model_mfr": " C29-0320B251 - HANSEN",
            "lead_time_str": "23/08/2028\n128 Weeks"
        },
        "expected": {
            "material_number": "1000148955",
            "uom": "each",
            "quantity": 2,
            "lead_time_date": "23/08/2028",
            "lead_time_weeks": 128,
            "sourcing_identifiers": [
                {"part_number": "C29-0320B251", "manufacturer": "HANSEN"}
            ],
            "flags": []
        }
    },
    {
        "description": "O Ring Suction Flange — hyphenated part number",
        "input": {
            "material_number": "1000198119",
            "long_description": "O RING;SUCTION FLANGE,2 IN,D3EHCS-162D",
            "uom": "each",
            "quantity": 10,
            "pn_model_mfr": " PP056TB1-225 - IMO PUMP",
            "lead_time_str": "28/05/2026\n11 Weeks"
        },
        "expected": {
            "material_number": "1000198119",
            "uom": "each",
            "quantity": 10,
            "lead_time_date": "28/05/2026",
            "lead_time_weeks": 11,
            "sourcing_identifiers": [
                {"part_number": "PP056TB1-225", "manufacturer": "IMO PUMP"}
            ],
            "flags": []
        }
    },
    {
        "description": "O Ring Discharge Flange — hyphenated part number",
        "input": {
            "material_number": "1000198120",
            "long_description": "O RING;DSCHRG FLANGE,1-1/2IN,D3EHCS-162D",
            "uom": "each",
            "quantity": 10,
            "pn_model_mfr": " PP056TB1-228 - IMO PUMP",
            "lead_time_str": "28/05/2026\n11 Weeks"
        },
        "expected": {
            "material_number": "1000198120",
            "uom": "each",
            "quantity": 10,
            "lead_time_date": "28/05/2026",
            "lead_time_weeks": 11,
            "sourcing_identifiers": [
                {"part_number": "PP056TB1-228", "manufacturer": "IMO PUMP"}
            ],
            "flags": []
        }
    },
]

# ---------------------------------------------------------------
# Edge case test cases — synthetic, tests flag logic
# ---------------------------------------------------------------

edge_test_cases = [
    {
        "description": "Edge case — blank PN/MODEL/MFR",
        "input": {
            "material_number": "9999999001",
            "long_description": "TEST ITEM — blank PN/MODEL/MFR",
            "uom": "each",
            "quantity": 1,
            "pn_model_mfr": "",
            "lead_time_str": "28/05/2026\n4 Weeks"
        },
        "expected": {
            "material_number": "9999999001",
            "uom": "each",
            "quantity": 1,
            "lead_time_date": "28/05/2026",
            "lead_time_weeks": 4,
            "sourcing_identifiers": [],
            "flags": ["missing_sourcing_identifier"]
        }
    },
    {
        "description": "Edge case — missing part number",
        "input": {
            "material_number": "9999999002",
            "long_description": "TEST ITEM — missing part number",
            "uom": "each",
            "quantity": 1,
            "pn_model_mfr": " - HANSEN",
            "lead_time_str": "28/05/2026\n4 Weeks"
        },
        "expected": {
            "material_number": "9999999002",
            "uom": "each",
            "quantity": 1,
            "lead_time_date": "28/05/2026",
            "lead_time_weeks": 4,
            "sourcing_identifiers": [
                {"part_number": None, "manufacturer": "HANSEN"}
            ],
            "flags": ["missing_part_number"]
        }
    },
    {
        "description": "Edge case — missing manufacturer",
        "input": {
            "material_number": "9999999003",
            "long_description": "TEST ITEM — missing manufacturer",
            "uom": "each",
            "quantity": 1,
            "pn_model_mfr": "C29-0320B251 - ",
            "lead_time_str": "28/05/2026\n4 Weeks"
        },
        "expected": {
            "material_number": "9999999003",
            "uom": "each",
            "quantity": 1,
            "lead_time_date": "28/05/2026",
            "lead_time_weeks": 4,
            "sourcing_identifiers": [
                {"part_number": "C29-0320B251", "manufacturer": None}
            ],
            "flags": ["missing_manufacturer"]
        }
    },
]

# Combined list for running all tests
all_test_cases = real_test_cases + edge_test_cases