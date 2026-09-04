# db/repositories/supplier_repository.py

"""
Repository layer for supplier lookups.

The point of this layer: API routes or workflow code should call
plain methods like find_by_manufacturer("ABB") instead of writing
SQLAlchemy queries directly inline. If the query logic changes later
(e.g. adding a join, changing how "stale" is defined), only this file
changes — not every place that needed a supplier lookup.
"""

from datetime import date
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Supplier


class SupplierRepository:
    def __init__(self, session: Session):
        self.session = session

    def find_by_manufacturer(self, manufacturer: str) -> List[Supplier]:
        statement = select(Supplier).where(Supplier.manufacturer == manufacturer)
        return list(self.session.scalars(statement).all())

    def find_stale_suppliers(self, cutoff_date: date) -> List[Supplier]:
        """
        Returns suppliers whose last_contact_date is before cutoff_date.

        Mirrors the 12-month staleness rule already used by the real
        supplier knowledge base (Module 2) — this just re-implements
        the same concept as a SQLAlchemy query instead of raw SQL.
        """
        statement = select(Supplier).where(Supplier.last_contact_date < cutoff_date)
        return list(self.session.scalars(statement).all())