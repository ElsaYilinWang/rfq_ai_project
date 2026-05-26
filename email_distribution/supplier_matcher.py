import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from email_distribution.schemas import MFRGroup, MatchedSupplier

STALE_THRESHOLD_DAYS = 365


def get_suppliers_for_manufacturer(manufacturer: str, db_path: Path) -> List[MatchedSupplier]:
    # connect to sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # run SQL query
    cursor.execute("""
        SELECT s.supplier_id, s.supplier_name, s.supplier_email, 
        i.priority, i.status, i.mfr_name, i.date_created 
        FROM supplier s JOIN interaction i 
        ON s.supplier_id = i.supplier_id WHERE i.mfr_name = ? 
        ORDER BY i.priority ASC
        """,
        (manufacturer,)
    )
    # for each row, calculate is_stale
    suppliers = []
    for row in cursor.fetchall():
        supplier_id, supplier_name, supplier_email, priority, status, mfr_name, date_created = row
        date_created = datetime.fromisoformat(date_created)
        is_stale = (datetime.now() - date_created) > timedelta(days=STALE_THRESHOLD_DAYS)
        suppliers.append(MatchedSupplier(
            supplier_id=supplier_id,
            name=supplier_name,
            email=supplier_email,
            priority=priority,
            is_stale=is_stale
        ))
    conn.close()
    return suppliers
       

    


def match_suppliers_to_groups(mfr_groups: List[MFRGroup], db_path: Path) -> List[MFRGroup]:
    # loop through each MFRGroup
    for group in mfr_groups:
        # call get_suppliers_for_manufacturer for each
        group.matched_suppliers = get_suppliers_for_manufacturer(group.manufacturer, db_path)
        # populate matched_suppliers


    # return updated list
    return mfr_groups