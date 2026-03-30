"""
Mock supplier test cases for Module 2
Follows same pattern as test_data.py for Module 1
"""
from datetime import datetime, timedelta

mock_test_cases = [
    {
        "description": "Insert supplier and retrieve by material number",
        "operations": [
            {
                "op": "insert_supplier",
                "params": {
                    "supplier_name": "Frick Electronics",
                    "supplier_email": "sales@frick.com",
                    "mfr_name": "FRICK"
                }
            },
            {
                "op": "insert_interaction",
                "params": {
                    "supplier_id": None,  # filled at runtime
                    "material_number": "1000124164",
                    "mfr_name": "FRICK",
                    "priority": "P2",
                    "status": "normal",
                    "previous_folder_number": "3275",
                    "reason": "Quoted before, competitive price"
                }
            },
            {
                "op": "search_by_material_number",
                "params": {"material_number": "1000124164"},
                "expected_count": 1,
                "expected_email": "sales@frick.com",
                "expected_status": "normal"
            }
        ]
    },
    {
        "description": "Insert supplier and retrieve by MFR fallback",
        "operations": [
            {
                "op": "insert_supplier",
                "params": {
                    "supplier_name": "Parker Hydraulics",
                    "supplier_email": "quote@parker.com",
                    "mfr_name": "PARKER"
                }
            },
            {
                "op": "insert_interaction",
                "params": {
                    "supplier_id": None,
                    "material_number": "1000124166",
                    "mfr_name": "PARKER",
                    "priority": "P2",
                    "status": "normal",
                    "previous_folder_number": "3100",
                    "reason": "Quoted before"
                }
            },
            {
                "op": "search_by_mfr",
                "params": {"mfr_name": "PARKER"},
                "expected_count": 1,
                "expected_email": "quote@parker.com",
                "expected_status": "normal"
            }
        ]
    },
    {
        "description": "Stale supplier flagged as needs validation",
        "operations": [
            {
                "op": "insert_supplier",
                "params": {
                    "supplier_name": "Old Supplier Ltd",
                    "supplier_email": "old@supplier.com",
                    "mfr_name": "FRICK"
                }
            },
            {
                "op": "insert_interaction_with_date",
                "params": {
                    "supplier_id": None,
                    "material_number": "1000100001",
                    "mfr_name": "FRICK",
                    "priority": "P1",
                    "status": "normal",
                    "previous_folder_number": "1000",
                    "reason": "Old PO",
                    "date_created": (
                        datetime.now() - timedelta(days=400)
                    ).isoformat()
                }
            },
            {
                "op": "search_by_material_number",
                "params": {"material_number": "1000100001"},
                "expected_count": 1,
                "expected_needs_validation": True
            }
        ]
    },
    {
        "description": "Search for material number with no history returns no results",
        "operations": [
            {
                "op": "search_by_material_number",
                "params": {"material_number": "9999999999"},
                "expected_count": 0,
                "expected_display": "No suppliers found."
            }
        ]
    },
    {
        "description": "MFR direct status stored and routed to special bucket",
        "operations": [
            {
                "op": "insert_supplier",
                "params": {
                    "supplier_name": "FRICK Direct",
                    "supplier_email": "direct@frick.com",
                    "mfr_name": "FRICK"
                }
            },
            {
                "op": "insert_interaction",
                "params": {
                    "supplier_id": None,
                    "material_number": "1000124170",
                    "mfr_name": "FRICK",
                    "priority": None,
                    "status": "mfr_direct",
                    "previous_folder_number": "3300",
                    "reason": "MFR only deals with end users directly"
                }
            },
            {
                "op": "search_by_material_number",
                "params": {"material_number": "1000124170"},
                "expected_count": 1,
                "expected_status": "mfr_direct",
                "expected_bucket": "special"
            }
        ]
    },
    {
        "description": "Discontinued status stored and routed to special bucket",
        "operations": [
            {
                "op": "insert_supplier",
                "params": {
                    "supplier_name": "Legacy Parts Co",
                    "supplier_email": "parts@legacy.com",
                    "mfr_name": "FRICK"
                }
            },
            {
                "op": "insert_interaction",
                "params": {
                    "supplier_id": None,
                    "material_number": "1000124171",
                    "mfr_name": "FRICK",
                    "priority": None,
                    "status": "discontinued",
                    "previous_folder_number": "3301",
                    "reason": "Product line discontinued as of 2023"
                }
            },
            {
                "op": "search_by_material_number",
                "params": {"material_number": "1000124171"},
                "expected_count": 1,
                "expected_status": "discontinued",
                "expected_bucket": "special"
            }
        ]
    }
]