# tests/test_supplier_repository.py

"""
Tests for the Phase 9 SQLAlchemy supplier repository layer.

Uses a fresh in-memory SQLite database per test (not the real
knowledge_base/suppliers.db), seeded with a few mock/sanitized
supplier records, to prove the repository's query methods work
correctly before anything in the real workflow depends on them.
"""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, Supplier
from db.repositories.supplier_repository import SupplierRepository


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    db_session = session_factory()

    # Mock/sanitized records only — not real supplier data.
    db_session.add_all([
        Supplier(
            supplier_name="Mock ABB Supplier",
            manufacturer="ABB",
            email="mock.abb.supplier@example.com",
            country="Ireland",
            last_contact_date=date(2026, 6, 1),   # recent -> not stale
        ),
        Supplier(
            supplier_name="Mock Second ABB Supplier",
            manufacturer="ABB",
            email="mock.abb.supplier2@example.com",
            country="Saudi Arabia",
            last_contact_date=date(2026, 5, 1),   # recent -> not stale
        ),
        Supplier(
            supplier_name="Mock Siemens Supplier",
            manufacturer="Siemens",
            email="mock.siemens.supplier@example.com",
            country="Germany",
            last_contact_date=date(2023, 1, 1),   # old -> stale
        ),
    ])
    db_session.commit()

    yield db_session
    db_session.close()


def test_find_by_manufacturer_returns_matching_suppliers(session):
    repository = SupplierRepository(session)

    results = repository.find_by_manufacturer("ABB")

    assert len(results) == 2
    assert all(supplier.manufacturer == "ABB" for supplier in results)


def test_find_by_manufacturer_returns_empty_for_unknown_manufacturer(session):
    repository = SupplierRepository(session)

    results = repository.find_by_manufacturer("Nonexistent Corp")

    assert results == []


def test_find_stale_suppliers_returns_only_suppliers_before_cutoff(session):
    repository = SupplierRepository(session)

    cutoff = date(2025, 1, 1)
    results = repository.find_stale_suppliers(cutoff)

    assert len(results) == 1
    assert results[0].supplier_name == "Mock Siemens Supplier"