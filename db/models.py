# db/models.py

"""
Minimal SQLAlchemy model for the Phase 9 supplier repository layer.

This is a small, separate demonstration of a database-backed supplier
table — it does not read from or write to the real
knowledge_base/suppliers.db used by supplier_discovery.py. Connecting
the two is future work, not part of this phase.
"""

from datetime import date

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Supplier(Base):
    __tablename__ = "suppliers"

    supplier_id: Mapped[int] = mapped_column(primary_key=True)
    supplier_name: Mapped[str]
    manufacturer: Mapped[str]
    email: Mapped[str]
    country: Mapped[str]
    last_contact_date: Mapped[date]