"""
Mock supplier test cases for Module 2
Follows same pattern as test_data.py for Module 1
"""
from datetime import datetime, timedelta

mock_supplier_test_cases = [
    {
        "description": "Insert supplier and retrieve by material number",
        "input": {
            "supplier_name": "Frick Electronics",
            "supplier_email": "sales@frick.com",
            "mfr_name": "FRICK",
            "material_number": "1000124164",
            "priority": "P2",
            "previous_folder_number": "3275",
            "reason": "Quoted before, competitive price"
        },
        "search": {
            "type": "material_number",
            "value": "1000124164"
        },
        "expected": {
            "result_count": 1,
            "supplier_email": "sales@frick.com",
            "priority": "P2",
            "needs_validation": False
        }
    },
    {
        "description": "Insert supplier and retrieve by MFR fallback",
        "input": {
            "supplier_name": "Parker Hydraulics",
            "supplier_email": "quote@parker.com",
            "mfr_name": "PARKER",
            "material_number": "2000567890",
            "priority": "P1",
            "previous_folder_number": "1636",
            "reason": "Previous PO for PARKER item 2000567890"
        },
        "search": {
            "type": "mfr",
            "value": "PARKER"
        },
        "expected": {
            "result_count": 1,
            "supplier_email": "quote@parker.com",
            "priority": "P1",
            "needs_validation": False
        }
    },
    {
        "description": "Stale supplier flagged as needs validation",
        "input": {
            "supplier_name": "Old Supplier Ltd",
            "supplier_email": "old@supplier.com",
            "mfr_name": "OLDMFR",
            "material_number": "3000999999",
            "priority": "P2",
            "previous_folder_number": "0500",
            "reason": "Quoted before — record is old",
            "override_date": datetime.now() - timedelta(days=400)
        },
        "search": {
            "type": "material_number",
            "value": "3000999999"
        },
        "expected": {
            "result_count": 1,
            "supplier_email": "old@supplier.com",
            "priority": "P2",
            "needs_validation": True
        }
    },
    {
        "description": "Search for material number with no history returns no results",
        "input": None,
        "search": {
            "type": "material_number",
            "value": "9999999999"
        },
        "expected": {
            "result_count": 0,
            "needs_validation": False
        }
    }
]