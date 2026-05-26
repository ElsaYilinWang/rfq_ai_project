import sys
import time
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from email_distribution.supplier_matcher import get_suppliers_for_manufacturer, match_suppliers_to_groups
from email_distribution.schemas import MatchedSupplier

TEST_DB_PATH = Path(__file__).parent.parent / "knowledge_base" / "test_suppliers.db"

def setup_test_db():
    """Create test database with supplier and interaction tables."""
    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()
    
    # create supplier table — exact same schema as Module 2
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS supplier (
            supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_name TEXT NOT NULL,
            supplier_email TEXT NOT NULL,
            mfr_name TEXT NOT NULL,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # create interaction table — exact same schema as Module 2
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS interaction (
            interaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER NOT NULL,
            material_number TEXT NOT NULL,
            mfr_name TEXT NOT NULL,
            priority TEXT CHECK(priority IN ('P1', 'P2', 'P3')),
            status TEXT NOT NULL DEFAULT 'normal',
            previous_folder_number TEXT,
            reason TEXT,
            date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(supplier_id) REFERENCES supplier(supplier_id)
        )
    ''')
    
    conn.commit()
    conn.close()


def insert_mock_data():
    """Insert mock suppliers and interactions for testing."""
    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()

    # --- FRICK supplier (P1, not stale) ---
    cursor.execute(
        "INSERT INTO supplier (supplier_name, supplier_email, mfr_name) VALUES (?, ?, ?)",
        ("FRICK Ltd", "sales@frick.com", "FRICK")
    )
    frick_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO interaction (supplier_id, material_number, mfr_name, priority, status, date_created) VALUES (?, ?, ?, ?, ?, ?)",
        (frick_id, "1000124164", "FRICK", "P1", "normal", "2025-12-01 09:00:00")
    )

    # --- PARKER P1 (not stale) ---
    cursor.execute(
        "INSERT INTO supplier (supplier_name, supplier_email, mfr_name) VALUES (?, ?, ?)",
        ("Parker Global", "sales@parker.com", "PARKER")
    )
    parker1_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO interaction (supplier_id, material_number, mfr_name, priority, status, date_created) VALUES (?, ?, ?, ?, ?, ?)",
        (parker1_id, "1000124166", "PARKER", "P1", "normal", "2025-12-01 09:00:00")
    )

    # --- PARKER P2 (stale) ---
    cursor.execute(
        "INSERT INTO supplier (supplier_name, supplier_email, mfr_name) VALUES (?, ?, ?)",
        ("Parker EU", "jason.will@exp1.com", "PARKER")
    )
    parker2_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO interaction (supplier_id, material_number, mfr_name, priority, status, date_created) VALUES (?, ?, ?, ?, ?, ?)",
        (parker2_id, "1000124166", "PARKER", "P2", "normal", "2024-12-15 09:00:00")
    )

    # --- PARKER P3 (not stale) ---
    cursor.execute(
        "INSERT INTO supplier (supplier_name, supplier_email, mfr_name) VALUES (?, ?, ?)",
        ("Parker Asia", "bharte@exp2.com", "PARKER")
    )
    parker3_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO interaction (supplier_id, material_number, mfr_name, priority, status, date_created) VALUES (?, ?, ?, ?, ?, ?)",
        (parker3_id, "1000124166", "PARKER", "P3", "normal", "2025-12-01 09:00:00")
    )

    conn.commit()
    conn.close()

def teardown_test_db():
    """Delete test database after tests complete."""
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


def run_tests():
    passed = 0
    failed = 0

    def check(description, actual, expected):
        nonlocal passed, failed
        if actual == expected:
            print(f"  PASS — {description}")
            passed += 1
        else:
            print(f"  FAIL — {description}")
            print(f"         expected: {expected}")
            print(f"         actual:   {actual}")
            failed += 1

    print("\nTEST REPORT — Supplier Matcher Module")
    print("=" * 40)

    # --- setup ---
    setup_test_db()
    insert_mock_data()

    # --- test FRICK ---
    frick_results = get_suppliers_for_manufacturer("FRICK", TEST_DB_PATH)
    check("FRICK returns 1 supplier", len(frick_results), 1)
    check("FRICK supplier email correct", frick_results[0].email, "sales@frick.com")
    check("FRICK supplier priority is P1", frick_results[0].priority, "P1")
    check("FRICK supplier is not stale", frick_results[0].is_stale, False)

    # --- test PARKER ---
    parker_results = get_suppliers_for_manufacturer("PARKER", TEST_DB_PATH)
    check("PARKER returns 3 suppliers", len(parker_results), 3)
    check("PARKER first supplier is P1", parker_results[0].priority, "P1")

    # find stale supplier
    stale = next((s for s in parker_results if s.email == "jason.will@exp1.com"), None)
    check("PARKER P2 supplier exists", stale is not None, True)
    check("PARKER P2 supplier is stale", stale.is_stale if stale else None, True)

    # --- teardown ---
    teardown_test_db()

    # --- summary ---
    print("=" * 40)
    print(f"Total cases: {passed + failed}")
    print(f"Passed: {passed}/{passed + failed}")
    print(f"Failed: {failed}/{passed + failed}")
    print(f"Result: {'ALL TESTS PASSED' if failed == 0 else 'SOME TESTS FAILED'}")


if __name__ == "__main__":
    run_tests()