# Warehouse Binning

Bin-level putaway and pick tracking layered on top of ERPNext stock. Tracks every item+batch to a specific rack/bin location — so any technician can find material without searching the warehouse.

---

## End-to-End Standard Operating Procedure (SOP)

This SOP covers everything from initial setup through go-live to daily warehouse operations.

### Contents

1. [System Requirements](#system-requirements)
2. [Installation](#installation)
3. [Pre-Go-Live Setup](#pre-go-live-setup)
4. [Go-Live: Backfill Existing Stock](#go-live-backfill-existing-stock)
5. [Daily Operations: Receiving (Putaway)](#daily-operations-receiving-putaway)
6. [Daily Operations: Issuing (Pick)](#daily-operations-issuing-pick)
7. [Daily Operations: Traceability (Lookup)](#daily-operations-traceability-lookup)
8. [Offline Mode & Troubleshooting](#offline-mode--troubleshooting)
9. [Architecture Reference](#architecture-reference)
10. [Development Guide](#development-guide)

---

### System Requirements

| Component | Version |
|---|---|
| ERPNext | v15 or later |
| Frappe Framework | v15 or later |
| Python | 3.10+ |
| Node.js | 18+ (for asset building) |
| Browser | Chrome, Edge, or Safari (mobile or desktop) |

---

### Installation

#### Step 1: Install the app

```bash
bench get-app https://github.com/balaji-001-gif/wms_bin
bench --site your-site install-app warehouse_binning
bench --site your-site migrate
```

The `migrate` step:
- Creates the **Warehouse Technician** role (no Desk access)
- Installs `bin_location` custom field on **Pick List Item** and **Stock Entry Detail**

#### Step 2: Verify installation

```bash
bench --site your-site console
```

In the console, run:

```python
import frappe
frappe.db.exists("Role", "Warehouse Technician")  # Should return True
frappe.db.exists("Custom Field", {"dt": "Pick List Item", "fieldname": "bin_location"})  # Should return True
```

#### Step 3: Assign technician roles

1. Go to **Frappe Desk > User > [Technician's User]**
2. Under **Roles**, add **Warehouse Technician**
3. Save

> Technicians do NOT need Desk access — they use the scanning UI at `https://your-site/scan`

---

### Pre-Go-Live Setup

#### Step 1: Create bin locations

Map your physical warehouse racks to Bin Location records.

**In the Desk:**
1. Go to **Warehouse Binning > Bin Location > Add New**
2. Create one entry per physical bin

**Naming convention:** `{WarehouseCode}-{Zone}{Rack}{Bin}`

Example for Warehouse "Stores - W", Zone A, Rack 01, Bin 001:
```
Stores - W-A-01-001
```

**Fields:**

| Field | Example | Description |
|---|---|---|
| Warehouse | Stores - W | Link to ERPNext Warehouse |
| Zone | A | Warehouse zone (A, B, C, etc.) |
| Rack | A-01 | Physical rack identifier |
| Bin Code | A-01-001 | Unique bin identifier within warehouse |
| Capacity | 1000 | (Optional) Max qty this bin can hold |
| Is Active | ✓ | Enable/disable for scanning |

**Capacity enforcement:** If you set a capacity, the system will reject putaway scans that would overfill the bin. Leave blank for unlimited capacity.

**Bulk import via Data Import:**
1. Go to **Frappe Desk > Data Import**
2. Select **Bin Location** as the DocType
3. Download template and upload your warehouse layout

#### Step 2: Configure bin capacity (optional)

For each Bin Location, set the **Capacity** field to the maximum quantity the bin can physically hold.

During putaway scanning, if the bin already has 800 units and capacity is 1000, scanning 250 more will be rejected with:
```
Bin Stores - W-A-01-001 capacity (1000) would be exceeded.
Current usage: 800, trying to add: 250.
```

#### Step 3: Verify scanning UI access

1. Log in as a **Warehouse Technician** user
2. Navigate to `https://your-site/scan`
3. You should see 3 tabs at the bottom: 📥 Putaway, 📤 Pick, 🔍 Lookup
4. The header should show **Online**

---

### Go-Live: Backfill Existing Stock

**Problem:** Before go-live, your warehouse already has stock on shelves. ERPNext knows the total qty per item+batch, but the binning system has zero records. Until items are scanned into bins, the Pick and Lookup views will show nothing.

**Solution:** Run the backfill patch to create placeholder records.

#### Run the backfill patch

```bash
bench --site your-site console
```

```python
from warehouse_binning.warehouse_binning.patches.backfill_item_batch_bin_stock import execute
execute()
```

**What the patch does:**
1. Scans `tabStock Ledger Entry` for all warehouses with positive qty
2. Creates an **inactive** placeholder bin: `{Warehouse}-UNKNOWN`
3. Moves existing item+batch qty into that bin in `Item Batch Bin Stock`
4. Writes audit entries to `Bin Stock Ledger Entry`

#### After backfill: physical audit

1. Print bin location labels for all racks
2. Physically verify each item+batch is in its correct bin
3. For items in the correct bin, do a **zero-qty putaway scan** to move from UNKNOWN to real bin
4. For misplaced items, move them physically and update in the system

> The backfill ensures day-one non-zero data for Pick suggestions and Lookup. The physical audit corrects any inaccuracies.

---

### Daily Operations: Receiving (Putaway)

**Trigger:** A Purchase Receipt is submitted in ERPNext.

#### System flow (automatic)

```
1. PR submitted by Procurement team
2. Event hook fires: purchase_receipt.create_putaway_tasks()
3. Putaway Task created (one per warehouse on the PR)
4. Status: "Pending"
```

#### Technician flow (scanning UI)

1. Open `https://your-site/scan`
2. Tap **📥 Putaway** tab
3. Open Putaway Tasks appear with status badges (Pending / Partially Completed)
4. Tap a task card to expand items

**For each item row:**
5. Take the item to the physical bin location
6. Tap **Scan Bin** → a dialog opens
7. Scan or type the bin barcode → **Confirm**

**Capacity check:** If the bin has a Capacity set and adding the item would exceed it, the scan is rejected with a clear message.

8. The item row updates to ✓ Scanned, and the progress bar advances
9. When all items are scanned, the task status changes to **Completed**

#### What happens in the system

```
Putaway Task item scanned
  → Item Batch Bin Stock updated (+qty)
  → Bin Stock Ledger Entry created (immutable audit trail)
```

---

### Daily Operations: Issuing (Pick)

**Trigger:** A Work Order is submitted OR a Material Request (Material Issue type) is submitted in ERPNext.

#### System flow (automatic)

```
Work Order submitted
  → Event hook fires: work_order.create_pick_tasks()
  → Pick Task created with suggested bins (FEFO)
  → Status: "Pending"

Material Request (Material Issue) submitted
  → Event hook fires: material_request.create_pick_tasks()
  → Pick Task created with suggested bins (FEFO)
  → Status: "Pending"
```

**FEFO logic:** The system suggests the bin holding the **earliest-expiring batch** first. Batches without expiry dates are sorted last.

#### Technician flow (scanning UI)

1. Open `https://your-site/scan`
2. Tap **📤 Pick** tab
3. (Optional) Filter by warehouse using the search bar
4. Open Pick Tasks appear with reference (WO / MR number)
5. Tap a task card to expand items

**For each item row:**
6. Go to the suggested bin location
7. Tap **Pick** → a dialog opens
8. Scan or type the bin barcode to confirm

**Bin validation:** The scanned bin must match the suggested bin. If it doesn't match, the scan is rejected.

9. The item row updates to ✓ Picked, and bin stock is deducted
10. When all items are picked, the task status changes to **Completed**

#### Creating the Stock Entry

After all items in a Pick Task are picked:
1. Go to the Frappe Desk
2. Create a **Stock Entry** (Material Issue or Material Transfer for Manufacture)
3. The bin_location field on each row will show the bin from which the item was picked
4. On submit, the system validates bin qty and updates the ledger

---

### Daily Operations: Traceability (Lookup)

Use the Lookup view to find where any item or batch is stored.

1. Open `https://your-site/scan`
2. Tap **🔍 Lookup** tab
3. Scan or type an item code or batch number → press Enter or tap Search

**Results show:**
- **Total Qty** — sum across all bins
- **Bins** — number of unique bin locations
- **Entries** — number of item+batch+bin combinations
- **Table** — every bin with stock, showing Bin, Item, Batch, and Qty

---

### Offline Mode & Troubleshooting

#### Offline behavior

| Situation | What happens |
|---|---|
| Device goes offline | Header badge changes to **Offline** |
| Technician scans an item | Scan is queued locally (IndexedDB) |
| Queue badge shows count | Red badge in header shows pending scans |
| Connection restores | Queue auto-syncs, badge clears, tasks refresh |

#### Common issues

| Issue | Cause | Resolution |
|---|---|---|
| "You do not have permission" | User missing Warehouse Technician role | Go to User > Roles, add the role |
| Scan rejected with capacity error | Bin Capacity set and would be exceeded | Use a different bin, or increase capacity |
| "Bin mismatch" during pick | Scanned bin ≠ suggested bin | Verify the correct bin, or update the bin suggestion |
| Queue not syncing | Session may have expired | Refresh the page and log in again |
| No Putaway Tasks appearing | No Purchase Receipts submitted | Submit a PR in the Desk first |
| No Pick Tasks appearing | No Work Orders or Material Requests | Submit a WO or MR in the Desk first |

---

### Architecture Reference

#### Data Flow Diagram

```
                    ┌──────────────────┐
                    │  Purchase Receipt │
                    │  (ERPNext)        │
                    └────────┬─────────┘
                             │ on_submit
                             ▼
                    ┌──────────────────┐
                    │  Putaway Task    │
                    │  (Pending)       │
                    └────────┬─────────┘
                             │ Technician scans bin
                             │ (capacity enforced)
                             ▼
                    ┌──────────────────┐
                    │  Item Batch Bin  │ ← Stock added (+qty)
                    │  Stock           │
                    └──────────────────┘


                    ┌──────────────────┐
                    │  Work Order /    │
                    │  Material Request│
                    └────────┬─────────┘
                             │ on_submit
                             ▼
                    ┌──────────────────┐
                    │  Pick Task       │
                    │  (FEFO bins)     │
                    └────────┬─────────┘
                             │ Technician picks from bin
                             ▼
                    ┌──────────────────┐
                    │  Item Batch Bin  │ ← Stock deducted (-qty)
                    │  Stock           │
                    └──────────────────┘
```

#### Doctypes

| Doctype | Type | Purpose | Key Fields |
|---|---|---|---|
| Bin Location | Master | Physical rack/bin | Warehouse, Zone, Rack, Bin Code, Capacity, Is Active |
| Putaway Task | Document | Receive-to-bin task | Purchase Receipt, Warehouse, Status |
| Putaway Task Item | Child | Items to bin | Item, Batch, Qty, Suggested Bin, Actual Bin, Scanned |
| Pick Task | Document | Pick-from-bin task | Work Order, Material Request, Warehouse, Status |
| Pick Task Item | Child | Items to pick | Item, Batch, Qty, From Bin, To Warehouse, Scanned |
| Bin Pick List Item | Child | General pick record | Item, Batch, Qty, From Bin, Source Document |
| Item Batch Bin Stock | Balance | (item,batch,warehouse,bin) → qty | Item, Batch, Warehouse, Bin, Qty |
| Bin Stock Ledger Entry | Ledger | Immutable audit trail | Item, Batch, Warehouse, Bin, Qty Change, Voucher |

#### Event Hooks

| Document | Event | Handler | Effect |
|---|---|---|---|
| Purchase Receipt | on_submit | `events.purchase_receipt.create_putaway_tasks` | Creates Putaway Tasks per warehouse |
| Stock Entry | before_submit | `events.stock_entry.validate_bin_pick` | Validates bin qty ≥ issue qty |
| Stock Entry | on_submit | `events.stock_entry.update_bin_ledger` | Deducts from bin ledger |
| Stock Entry | on_cancel | `events.stock_entry.reverse_bin_ledger` | Reverses bin deduction |
| Pick List | validate | `events.pick_list.suggest_bins` | FEFO bin suggestion |
| Work Order | on_submit | `events.work_order.create_pick_tasks` | Creates Pick Tasks |
| Material Request | on_submit | `events.material_request.create_pick_tasks` | Creates Pick Tasks |

#### API Endpoints (locked to roles)

| Endpoint | Method | Roles Required |
|---|---|---|
| `get_open_putaway_tasks` | POST | Stock Manager, Stock User, Warehouse Technician |
| `get_putaway_task_detail` | POST | Same |
| `scan_putaway_item` | POST | Same (enforces bin capacity) |
| `get_open_pick_tasks` | POST | Same |
| `get_pick_task_detail` | POST | Same |
| `scan_pick_item` | POST | Same |
| `lookup_bin_stock` | POST | Same |

All endpoints require a valid Frappe session. Role check is enforced server-side via `_require_role()`.

#### Permissions

| Role | Bin Location | Putaway Task | Pick Task | Item Stock | Ledger | Desk Access |
|---|---|---|---|---|---|---|
| **Warehouse Technician** | Read | R/W | R/W | Read | Read | ❌ |
| **Stock User** | R/W/C | R/W/C | R/W/C | Read | Read | ✅ |
| **Stock Manager** | Full | Full | Full | Read | Read | ✅ |
| **System Manager** | — | — | — | Full | Full | ✅ |

---

### Development Guide

#### Project structure

```
warehouse_binning/
├── warehouse_binning/
│   ├── __init__.py
│   ├── hooks.py            # App config, roles, event registration
│   ├── api.py              # Whitelisted endpoints (role-gated)
│   ├── utils.py            # Core ledger + lookup functions
│   ├── patches.txt         # Migration patch registry
│   ├── patches/            # Data migration scripts
│   ├── events/             # ERPNext event hook handlers
│   ├── fixtures/           # Custom field JSON exports
│   ├── www/                # Web-facing pages (scan.html)
│   └── doctype/            # All custom doctypes
├── .github/workflows/ci.yml
├── pyproject.toml
├── README.md
└── license.txt
```

#### Adding a new doctype

```bash
bench new-doctype DoctypeName --module "Warehouse Binning"
```

Move generated files to `warehouse_binning/warehouse_binning/doctype/doctype_name/`.

#### Running migrations after changes

```bash
bench --site your-site migrate
```

#### Backfill patch (go-live only)

```python
bench --site your-site console
>>> from warehouse_binning.warehouse_binning.patches.backfill_item_batch_bin_stock import execute
>>> execute()
```

---

## License

MIT
