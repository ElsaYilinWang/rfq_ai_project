import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# Constants
DB_PATH = Path("knowledge_base/suppliers.db")
STALENESS_DAYS = 365  # 12 months

class SupplierDiscoveryDB:
    """Handle all database operations for Module 2"""
    
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(exist_ok=True)
        self.init_db()
    
    def init_db(self):
        """Create tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS supplier (
                supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_name TEXT NOT NULL,
                supplier_email TEXT NOT NULL,
                mfr_name TEXT NOT NULL,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS interaction (
                interaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER NOT NULL,
                material_number TEXT NOT NULL,
                mfr_name TEXT NOT NULL,
                priority TEXT NOT NULL CHECK(priority IN ('P1', 'P2', 'P3')),
                previous_folder_number TEXT,
                reason TEXT,
                date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(supplier_id) REFERENCES supplier(supplier_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def insert_supplier(self, supplier_name, supplier_email, mfr_name):
        """Add new supplier to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO supplier (supplier_name, supplier_email, mfr_name)
            VALUES (?, ?, ?)
        ''', (supplier_name, supplier_email, mfr_name))
        
        supplier_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return supplier_id
    
    def insert_interaction(self, supplier_id, material_number, mfr_name, priority, previous_folder_number=None, reason=None):
        """Record interaction with supplier for specific material"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO interaction 
            (supplier_id, material_number, mfr_name, priority, previous_folder_number, reason)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (supplier_id, material_number, mfr_name, priority, previous_folder_number, reason))
        
        conn.commit()
        conn.close()
    
    def search_by_material_number(self, material_number):
        """Search knowledge base by material number — primary search"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT s.supplier_id, s.supplier_name, s.supplier_email, s.mfr_name,
                   i.priority, i.reason, i.date_created, i.previous_folder_number
            FROM supplier s
            JOIN interaction i ON s.supplier_id = i.supplier_id
            WHERE i.material_number = ?
            ORDER BY i.date_created DESC
        ''', (material_number,))
        
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    def search_by_mfr(self, mfr_name):
        """Search knowledge base by MFR — fallback search"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT s.supplier_id, s.supplier_name, s.supplier_email, s.mfr_name,
                   i.priority, i.reason, i.date_created, i.previous_folder_number
            FROM supplier s
            JOIN interaction i ON s.supplier_id = i.supplier_id
            WHERE s.mfr_name = ?
            ORDER BY i.date_created DESC
        ''', (mfr_name,))
        
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    def display_results_ranked(self, results):
        """Format and rank results P1/P2/P3 with staleness flag"""
        if not results:
            return "No suppliers found."
        
        ranked = {'P1': [], 'P2': [], 'P3': []}
        now = datetime.now()
        
        for row in results:
            result_dict = dict(row)
            supplier_id = result_dict['supplier_id']
            priority = result_dict['priority']
            date_created = datetime.fromisoformat(result_dict['date_created'])
            days_old = (now - date_created).days
            
            # Flag if older than 12 months
            needs_validation = days_old > STALENESS_DAYS
            
            result_dict['days_old'] = days_old
            result_dict['needs_validation'] = needs_validation
            result_dict['supplier_id_formatted'] = f"SUP-{supplier_id:03d}"
            
            ranked[priority].append(result_dict)
        
        return ranked