"""
Seed knowledge base with mock historical supplier data for testing.
Run once to pre-populate suppliers.db before testing AI suggestions.
"""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path("knowledge_base/suppliers.db")
HISTORICAL_PATH = Path("mock_data/historical_supplier_items.json")


def seed():
    with HISTORICAL_PATH.open() as f:
        items = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for item in items:
        cursor.execute('''
            INSERT INTO supplier (supplier_name, supplier_email, mfr_name)
            VALUES (?, ?, ?)
        ''', (item['supplier_name'], item['supplier_email'], item['manufacturer']))

        supplier_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO interaction
            (supplier_id, material_number, mfr_name, priority, status, reason)
            VALUES (?, ?, ?, ?, 'normal', ?)
        ''', (
            supplier_id,
            item.get('part_number', 'UNKNOWN'),
            item['manufacturer'],
            item['priority'],
            item['description']
        ))

    conn.commit()
    conn.close()
    print(f"✅ Seeded {len(items)} historical items into knowledge base.")


if __name__ == "__main__":
    seed()