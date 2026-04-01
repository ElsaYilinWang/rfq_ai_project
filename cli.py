"""
Supplier Discovery CLI
======================
Command-line interface for Module 2 supplier discovery workflow.
Loads parsed RFQ JSON, searches knowledge base, captures new suppliers.
"""

import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from supplier_discovery import SupplierDiscoveryDB


class SupplierDiscoveryCLI:
    """Main CLI orchestration for supplier discovery"""
    
    def __init__(self):
        self.db = SupplierDiscoveryDB()
        self.final_suppliers = []
        self.current_rfq_number = None
        self.parsed_rfq = None
    
    def load_parsed_json(self, rfq_number):
        """Load parsed RFQ JSON from output folder"""
        json_path = Path(f"mock_data/parsed_{rfq_number}.json")
        
        if not json_path.exists():
            print(f"❌ RFQ file not found: {json_path}")
            return False
        
        try:
            with open(json_path, 'r') as f:
                self.parsed_rfq = json.load(f)
            self.current_rfq_number = rfq_number
            print(f"✅ Loaded RFQ {rfq_number}: {len(self.parsed_rfq['items'])} line items")
            return True
        except json.JSONDecodeError:
            print(f"❌ Invalid JSON in {json_path}")
            return False
    
    def display_line_item(self, item_number, item):
        """Display material number, part number, and manufacturer"""
        material = item.get("material_number", "N/A")
        
        # Extract part number and manufacturer from sourcing_identifiers
        part_number = "N/A"
        manufacturer = "N/A"
        
        sourcing = item.get("sourcing_identifiers", [])
        if sourcing:
            part_number = sourcing[0].get("part_number", "N/A")
            manufacturer = sourcing[0].get("manufacturer", "N/A")
        
        print(f"\n{'='*60}")
        print(f"Line Item {item_number}")
        print(f"{'='*60}")
        print(f"Material Number: {material}")
        print(f"Part Number:     {part_number}")
        print(f"Manufacturer:    {manufacturer}")
        print(f"{'-'*60}")
    
    def search_and_display(self, material_number, manufacturer):
        """Search knowledge base and display results"""
        print("\nSearching knowledge base...")
        
        # Primary search by material number
        results = self.db.search_by_material_number(material_number)
        
        # Fallback to MFR if no results
        if not results:
            print(f"  No results for material {material_number}")
            print(f"  Falling back to manufacturer {manufacturer}...")
            results = self.db.search_by_mfr(manufacturer)
        
        # Display results
        ranked = self.db.display_results_ranked(results)
        
        if isinstance(ranked, str):
            # "No suppliers found."
            print(f"\n⚠️  {ranked}")
            return []
        
        # Display ranked results
        display_results = []
        index = 1
        
        for tier in ['P1', 'P2', 'P3']:
            for result in ranked.get(tier, []):
                staleness_flag = " ⚠️ NEEDS VALIDATION" if result['needs_validation'] else ""
                print(f"  [{index}] {tier} | {result['supplier_id_formatted']} | "
                      f"{result['supplier_name']} | {result['supplier_email']}{staleness_flag}")
                display_results.append(result)
                index += 1
        
        for result in ranked.get('special', []):
            status_display = result['status'].upper().replace('_', ' ')
            print(f"  [{index}] SPECIAL | {status_display} | {result['supplier_name']} | "
                  f"{result['supplier_email']}")
            display_results.append(result)
            index += 1
        
        return display_results
    
    def handle_special_status(self, status, reason):
        """Handle special status (mfr_direct or discontinued)"""
        if status == 'mfr_direct':
            print(f"\n⚠️  MFR DEALS DIRECTLY")
            print(f"  Reason: {reason}")
            print(f"  This manufacturer only sells direct to end users.")
            choice = input("  Skip this item? (y/n): ").strip().lower()
            return choice == 'y'
        
        elif status == 'discontinued':
            print(f"\n⚠️  ITEM DISCONTINUED")
            print(f"  Reason: {reason}")
            print(f"  Supplier may quote replacement or alternatives.")
            choice = input("  Continue? (y/n): ").strip().lower()
            return choice == 'y'
        
        return False
    
    def ask_user_action(self, display_results):
        """Show menu and get user choice"""
        print(f"\nOptions:")
        print(f"  [s] Select supplier from results")
        print(f"  [a] Add new supplier")
        print(f"  [n] Next line item")
        print(f"  [q] Quit")
        
        return self.get_valid_input("Enter choice (s/a/n/q): ", ['s', 'a', 'n', 'q'])
    
    def add_supplier_from_results(self, result):
        """Add selected result from knowledge base to final list"""
        print(f"\n✅ Adding to final list:")
        print(f"  Supplier: {result['supplier_name']}")
        print(f"  Email: {result['supplier_email']}")
        print(f"  Priority: {result['priority']}")
        
        self.final_suppliers.append({
            "supplier_id": result['supplier_id_formatted'],
            "supplier_name": result['supplier_name'],
            "supplier_email": result['supplier_email'],
            "priority": result['priority'],
            "status": result.get('status', 'normal')
        })
    
    def add_new_supplier(self, material_number, manufacturer):
        """Capture new supplier details and save to knowledge base"""
        print(f"\n--- Add New Supplier ---")
        
        supplier_name = input("Supplier name (required): ").strip()
        if not supplier_name:
            print("❌ Supplier name is required. Skipping.")
            return
        
        while True:
            supplier_email = input("Supplier email (required): ").strip()
            if not supplier_email:
                print("❌ Supplier email is required.")
            elif '@' not in supplier_email or '.' not in supplier_email.split('@')[-1]:
                print("❌ Invalid email format. Please try again.")
            else:
                break
        
        print("Priority: (1=P1, 2=P2, 3=P3)")
        priority_choice = self.get_valid_input(
            "Enter priority (1/2/3): ", 
            ['1', '2', '3']
        )
        priority = {'1': 'P1', '2': 'P2', '3': 'P3'}[priority_choice]
        
        
        reason = input("Reason (optional): ").strip()
        folder_number = input("Folder number (optional): ").strip()
        
        # Insert into database
        supplier_id = self.db.insert_supplier(
            supplier_name=supplier_name,
            supplier_email=supplier_email,
            mfr_name=manufacturer
        )
        
        self.db.insert_interaction(
            supplier_id=supplier_id,
            material_number=material_number,
            mfr_name=manufacturer,
            priority=priority,
            status='normal',
            previous_folder_number=folder_number if folder_number else None,
            reason=reason if reason else None
        )
        
        print(f"✅ Saved to knowledge base: {supplier_name}")
        
        # Add to final list
        self.final_suppliers.append({
            "supplier_id": f"SUP-{supplier_id:03d}",
            "supplier_name": supplier_name,
            "supplier_email": supplier_email,
            "priority": priority,
            "status": 'normal'
        })
    
    def select_from_results(self, display_results):
        """Let user select which results to add to final list"""
        if not display_results:
            print("❌ No results to select from.")
            return
        
        selection = input("Enter result number to add (or blank to skip): ").strip()
        
        if not selection:
            return
        
        try:
            index = int(selection) - 1
            if 0 <= index < len(display_results):
                self.add_supplier_from_results(display_results[index])
            else:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Please enter a valid number.")
    
    def output_final_list(self):
        """Write final supplier list to JSON file"""
        if not self.final_suppliers:
            print("⚠️  No suppliers selected for this RFQ.")
            return
        
        output = {
            "rfq_number": self.current_rfq_number,
            "generated_date": datetime.now().isoformat(),
            "suppliers": self.final_suppliers,
            "total_count": len(self.final_suppliers)
        }
        
        output_path = Path(f"output/suppliers_{self.current_rfq_number}.json")
        output_path.parent.mkdir(exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"\n✅ Final supplier list saved: {output_path}")
        print(f"   Total suppliers: {len(self.final_suppliers)}")
        for supplier in self.final_suppliers:
            print(f"   - {supplier['supplier_name']} ({supplier['priority']})")
    
    def process_rfq(self):
        """Main RFQ processing loop"""
        if not self.parsed_rfq:
            print("❌ No RFQ loaded.")
            return
        
        items = self.parsed_rfq.get("items", [])
        self.final_suppliers = []  # ← MOVE HERE: reset once per RFQ
        quit_flag = False  # ← ADD THIS
        
        for item_num, item in enumerate(items, start=1):
            
            material = item.get("material_number", "N/A")
            
            sourcing = item.get("sourcing_identifiers", [])
            manufacturer = "N/A"
            if sourcing:
                manufacturer = sourcing[0].get("manufacturer", "N/A")
            
            self.display_line_item(item_num, item)
            display_results = self.search_and_display(material, manufacturer)
            
            if display_results:
                for result in display_results:
                    if result.get('status') in ('mfr_direct', 'discontinued'):
                        should_skip = self.handle_special_status(
                            result['status'],
                            result.get('reason', 'N/A')
                        )
                        if should_skip:
                            break
            
            # User action loop
            while True:
                action = self.ask_user_action(display_results)
                
                if action == 's':
                    self.select_from_results(display_results)
                elif action == 'a':
                    self.add_new_supplier(material, manufacturer)
                elif action == 'n':
                    break
                elif action == 'q':
                    print("❌ Exiting.")
                    quit_flag = True  # ← CHANGE THIS
                    break
            
            if quit_flag:  # ← ADD THIS
                break      # ← ADD THIS
        
        self.output_final_list()
        sys.exit(0)
    
    def run(self):
        """Main entry point"""
        print("="*60)
        print("SUPPLIER DISCOVERY ASSISTANT")
        print("="*60)
        
        rfq_number = input("Enter RFQ number (e.g., 6000184918): ").strip()
        
        if not rfq_number:
            print("❌ RFQ number required.")
            return
        
        if not self.load_parsed_json(rfq_number):
            return
        
        self.process_rfq()
        
        print("\n✅ RFQ processing complete.")
    
    
    def get_valid_input(self, prompt, valid_options):
        """Keep asking until user enters a valid option"""
        while True:
            choice = input(prompt).strip().lower()
            if choice in valid_options:
                return choice
            print(f"❌ Invalid input. Please enter one of: {', '.join(valid_options)}")


if __name__ == "__main__":
    cli = SupplierDiscoveryCLI()
    cli.run()