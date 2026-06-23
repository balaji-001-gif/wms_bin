# Warehouse Binning

> **Bin-level putaway and pick tracking for ERPNext.**  
> Know exactly which rack and bin every item and batch lives in — so any technician can find material without searching the warehouse.

---

## Table of Contents

1. [Who This App Is For](#who-this-app-is-for)
2. [Start Here: Installation for IT Team](#start-here-installation-for-it-team)
3. [Pre-Go-Live Checklist (Warehouse Manager)](#pre-go-live-checklist-warehouse-manager)
4. [Go-Live Day: Backfill Existing Stock](#go-live-day-backfill-existing-stock)
5. [Transaction: Receive Goods (Putaway)](#transaction-receive-goods-putaway)
6. [Transaction: Issue Material (Pick)](#transaction-issue-material-pick)
7. [Transaction: Lookup Stock](#transaction-lookup-stock)
8. [Reports & Monitoring](#reports--monitoring)
9. [Notifications & Alerts](#notifications--alerts)
10. [Troubleshooting Guide](#troubleshooting-guide)
11. [Role & Permission Matrix](#role--permission-matrix)
12. [Technical Architecture (For IT Reference)](#technical-architecture-for-it-reference)

---

## Who This App Is For

| Role | What They Do in This App |
|---|---|
| **Warehouse Manager** | Setup bin locations, configure capacities, review reports, investigate discrepancies |
| **Warehouse Technician** | Daily scanning — putaway incoming goods, pick material for production/issues |
| **Procurement Team** | Submit Purchase Receipts (triggers putaway tasks automatically) |
| **Production Team** | Submit Work Orders / Material Requests (triggers pick tasks automatically) |
| **IT / Super User** | Install the app, assign roles, run go-live backfill, troubleshoot |

---

## Start Here: Installation for IT Team

### Step 1 — Install the app on your bench

```bash
bench get-app https://github.com/balaji-001-gif/wms_bin
bench --site your-site install-app warehouse_binning
bench --site your-site migrate
```

### Step 2 — Verify installation

```bash
bench --site your-site console
```

```python
frappe.db.exists("Role", "Warehouse Technician")  # → True
frappe.db.exists("Custom Field", {"dt": "Pick List Item", "fieldname": "bin_location"})  # → True
```

### Step 3 — Assign roles to users

| Go to | Do this |
|---|---|
| **Frappe Desk > User > [Technician's User]** | Add role **Warehouse Technician**, save |
| **Frappe Desk > User > [Warehouse Manager]** | Add role **Stock Manager**, save |
| **Frappe Desk > User > [Procurement Team]** | No change needed — they keep existing roles |

> **Important:** Warehouse Technicians do NOT need Desk access. They use only the scanning UI at `https://your-site/scan`

---

## Pre-Go-Live Checklist (Warehouse Manager)

Complete these steps BEFORE any technician starts scanning.

### □ 1. Map your warehouse into bin locations

Walk through your warehouse and identify every physical location where stock is stored.

**Naming convention:** `{WarehouseCode}-{Zone}{Rack}{Bin}`

| Physical location | Bin Location name |
|---|---|
| Stores warehouse, Zone A, Rack 01, position 001 | `Stores - W-A-01-001` |
| FG warehouse, Zone B, Rack 03, position 010 | `FG Warehouse - W-B-03-010` |

### □ 2. Create Bin Location records (two options)

**Option A — One by one in Desk:**
1. Go to **Warehouse Binning > Bin Location > + Add New**
2. Enter: Warehouse, Zone, Rack, Bin Code, Is Active ✓
3. Capacity is optional — see step 3

**Option B — Bulk import via spreadsheet:**
1. Go to **Frappe Desk > Data Import**
2. Select **Bin Location** as the DocType
3. Download template, fill in all your bins, upload

### □ 3. Set bin capacities (optional but recommended)

For each Bin Location, set the **Capacity** field to the maximum quantity the bin can physically hold.

Once set, the system **rejects putaway scans** that would overfill a bin:

```
Bin Stores - W-A-01-001 capacity (1000) would be exceeded.
Current usage: 800, trying to add: 250.
```

Leave capacity **blank** for bins that have no limit (e.g., bulk storage areas).

### □ 4. Print barcode labels

The app ships a **Bin Location Label** print format that generates a small label (62mm x 29mm) with:
- Warehouse name
- Bin location name in large text
- Code128 barcode of the bin name
- Zone / Rack info

**To print labels for all bins:**

1. Go to **Warehouse Binning > Bin Location**
2. Select the bins you want to label (check the boxes)
3. Click **Menu > Print > Bin Location Label**
4. Select your label printer

**To print a single label:**

1. Open a **Bin Location** record
2. Click **Print > Bin Location Label**
3. Select your label printer

Print on adhesive label sheets (Avery L7160 or similar) or direct thermal labels.

> The `fixtures/print_format.json` is installed automatically on `bench migrate`. If you don't see the print format, run `bench --site your-site migrate` again.

**Naming convention reminder:** `{Warehouse}-{BinCode}` → e.g. `Stores - W-A-01-001`

### □ 5. Affix labels to physical racks

1. Print all labels
2. Walk the warehouse and affix each label to its corresponding physical rack/bin
3. Verify each label is readable by your scanner device

### □ 6. Verify scanning UI access

### □ 7. Verify scanning UI access

1. Log in as a **Warehouse Technician** user
2. Open: `https://your-site/scan`
3. You should see 3 tabs: **📥 Putaway** / **📤 Pick** / **🔍 Lookup**
4. The header badge should show **Online** ✅

---

## Go-Live Day: Backfill Existing Stock

### Why this is needed

Your warehouse already has stock on shelves. ERPNext knows the total quantity per item+batch, but the binning system has no records yet. Until items are assigned to bins, the Pick and Lookup views will show nothing.

### Run the backfill patch

```bash
bench --site your-site console
```

```python
from warehouse_binning.warehouse_binning.patches.backfill_item_batch_bin_stock import execute
execute()
```

### What the patch does

1. Reads all positive stock from `Stock Ledger Entry`
2. Creates a placeholder bin: **`{Warehouse}-UNKNOWN`** (marked inactive so it doesn't appear in pick suggestions)
3. Moves all existing item+batch quantities into that placeholder bin
4. Writes audit entries to `Bin Stock Ledger Entry`

### After backfill: physical audit

| Step | Action |
|---|---|
| 1 | Print a bin location label for every physical rack |
| 2 | Walk the warehouse, verify each item+batch is in its correct bin |
| 3 | For items already in the correct bin, do a **zero-qty putaway scan** to move from UNKNOWN → real bin |
| 4 | For misplaced items, move them physically and scan them into the correct bin |

---

## Transaction: Receive Goods (Putaway)

### Who does what

| Team | Action | System |
|---|---|---|
| **Procurement** | Submit a Purchase Receipt in the Desk | ERPNext |
| **Warehouse Technician** | Scan items into bins using the scanning UI | Warehouse Binning |

### Step-by-step: Procurement

1. Create a **Purchase Receipt** as usual in ERPNext
2. Submit it

**Behind the scenes:** The system automatically creates a **Putaway Task** (one per warehouse on the PR) with all item rows and their suggested bins.

### Step-by-step: Warehouse Technician

**Where:** `https://your-site/scan` on any device (mobile, tablet, handheld scanner, desktop)

1. Tap the **📥 Putaway** tab
2. You'll see all open Putaway Tasks, each showing:
   - Purchase Receipt number
   - Warehouse
   - Status badge: Pending / Partially Completed / Completed
   - Progress bar (items scanned / total items)
3. Tap any task to expand its item list
4. For each item row:
   - Take the item to its physical bin location
   - Tap **Scan Bin**
   - Scan the bin barcode (or type it manually)
   - The system checks bin capacity — if the bin is full, you'll get an error
   - Tap **Confirm**

5. ✅ The row updates to **Scanned**, progress bar advances
6. When all items are scanned, the task status changes to **Completed**

### What happens in the system

```
Technician scans bin
  → Item Batch Bin Stock updated (+ quantity)
  → Bin Stock Ledger Entry created (audit — never deleted)
  → Putaway Task progress updated
```

---

## Transaction: Issue Material (Pick)

### Who does what

| Team | Action | System |
|---|---|---|
| **Production** | Submit a Work Order or Material Request in the Desk | ERPNext |
| **Warehouse Technician** | Pick items from bins using the scanning UI | Warehouse Binning |

### How pick tasks are created

| If you submit this... | This happens... |
|---|---|
| **Work Order** (status Planned or Material Requested) | Pick Task created per source warehouse, bins suggested using **FEFO** (earliest-expiring batch first) |
| **Material Request** (type: Material Issue) | Pick Task created per warehouse, bins suggested using FEFO |

### Step-by-step: Warehouse Technician

1. Open `https://your-site/scan`
2. Tap the **📤 Pick** tab
3. (Optional) Filter by warehouse using the search bar
4. Open Pick Tasks appear with:
   - Reference number (WO-xxxx / MR-xxxx)
   - Warehouse
   - Status badge: Pending / Partially Completed / Completed
   - Progress bar

5. Tap a task to expand items
6. For each item:
   - Go to the **suggested bin** (the system picks the bin with the earliest-expiring batch)
   - Tap **Pick**
   - Scan or type the bin barcode

   > **Bin validation:** The scanned bin must match the suggested bin. If it doesn't match, the scan is rejected.

7. ✅ The row updates to **Picked**, bin stock is deducted
8. When all items are picked, the task status changes to **Completed**

### After picking: create the Stock Entry

1. Go to the **Frappe Desk**
2. Create a **Stock Entry** (Material Issue or Material Transfer for Manufacture)
3. The `bin_location` field on each item row is pre-filled with the bin from which the item was picked
4. Submit the Stock Entry

**Behind the scenes:** On submit, the system validates the bin still has enough quantity and updates the bin ledger.

---

## Transaction: Lookup Stock

### Find any item or batch

1. Open `https://your-site/scan`
2. Tap the **🔍 Lookup** tab
3. Scan or type an item code or batch number
4. Press **Enter** or tap **Search**

### What you see

| Metric | Shows |
|---|---|
| **Total Qty** | Sum across all bins |
| **Bins** | Number of unique bin locations holding this item |
| **Entries** | Number of item+batch+bin combinations |

**Detailed table:**
| Bin | Item | Batch | Qty |
|---|---|---|---|
| Stores - W-A-01-001 | ITEM-001 | BATCH-2401 | 500 |
| Stores - W-A-01-002 | ITEM-001 | BATCH-2402 | 300 |

---

## Reports & Monitoring

### Built-in reports via the Desk

Open **Warehouse Binning** module in the Frappe Desk to access these reports:

| Report / View | What you see | Who uses it |
|---|---|---|
| **Bin Location** list | All bins with warehouse, zone, rack, capacity, active status | Warehouse Manager |
| **Putaway Task** list | All putaway tasks with status, warehouse, creation date, linked PR | Warehouse Manager |
| **Pick Task** list | All pick tasks with status, warehouse, linked WO/MR | Warehouse Manager |
| **Item Batch Bin Stock** list | Complete inventory — every item+batch+bin with current qty | Stock Manager |
| **Bin Stock Ledger Entry** list | Complete audit trail — every qty change with timestamp and voucher | Auditor / Stock Manager |

### How to run a bin-level stock report

1. Go to **Frappe Desk > Warehouse Binning > Item Batch Bin Stock**
2. Use the filters to narrow down:
   - By **Item Code** — see where a specific item is stored
   - By **Warehouse** — see full bin map of a warehouse
   - By **Bin Location** — see what's in a specific bin
3. Export to Excel using the **Export** button

### Stock aging by bin (manual)

1. **Item Batch Bin Stock** shows each item+batch+bin row with quantity
2. The **Batch** field links to ERPNext's Batch doctype where expiry date is recorded
3. You can cross-reference expiry dates to see which bins contain aging stock

---

## Notifications & Alerts

This app does **not send email/SMS notifications**. Instead, alerts are built into the user interface at the point of action.

### In-app alerts during scanning

| Situation | Alert | Who sees it |
|---|---|---|
| Bin is at full capacity | ❌ *"Bin X capacity (1000) would be exceeded. Current usage: 800, trying to add: 250."* | Technician (during putaway scan) |
| Scanned bin doesn't match suggested bin | ❌ *"Bin mismatch"* | Technician (during pick scan) |
| Device goes offline | 🔴 Header badge changes to **Offline** | Technician |
| Device comes back online | 🟢 Header badge changes to **Syncing**, then **Online** | Technician |
| Queued scans are processing | 🔄 Header badge shows **Syncing** with count | Technician |

### What to watch for (management awareness)

1. **Overfilled bins:** If a bin's capacity is set, the system blocks overfilling. If technicians report they can't scan, check if the capacity is set too low or if the bin needs to be split.
2. **UNKNOWN bin entries:** After go-live, the `{Warehouse}-UNKNOWN` bin holds stock that hasn't been assigned to a real bin. Track this count — it should trend toward zero as physical audit progresses.
3. **Pending putaway tasks:** If Purchase Receipts are submitted but putaway tasks remain pending, it means goods are in the warehouse but not yet binned. This is a normal backlogs metric.
4. **Pending pick tasks:** If Work Orders / Material Requests are submitted but picks are pending, production may be waiting on material.

### Checking task status

**In the Desk:**
1. Go to **Warehouse Binning > Putaway Task** (or **Pick Task**)
2. The **Status** field shows: Pending / Partially Completed / Completed
3. Use filters to find tasks not yet completed

**On the scanning UI:**
- Open tasks show on the **📥 Putaway** and **📤 Pick** tabs
- Each task card shows its status badge and progress bar

---

## Troubleshooting Guide

### Common errors & solutions

| Error message | Likely cause | What to do |
|---|---|---|
| `"You do not have permission"` | User missing Warehouse Technician role | Go to **User > [user] > Roles**, add **Warehouse Technician** |
| `"Bin X capacity would be exceeded"` | Bin Capacity is set and would be exceeded | Use a different bin, or ask Warehouse Manager to increase capacity on the Bin Location |
| `"Bin mismatch"` during pick | Scanned bin ≠ suggested bin from the Pick Task | Double-check the physical bin — if it's correct, the Pick Task may have wrong bin; ask manager to update |
| No tasks on Putaway tab | No Purchase Receipts submitted recently | Submit a PR in the Desk first |
| No tasks on Pick tab | No Work Orders or Material Requests submitted | Submit a WO or MR in the Desk first |
| Lookup shows no results | Item not yet in any bin | If item has stock in ERPNext, run the backfill patch. If new, receive it via Purchase Receipt first |
| Offline badge won't clear after reconnecting | Session may have expired or browser cache issue | Refresh the page and log in again |

### Offline mode behavior

| Situation | What happens |
|---|---|
| **Device goes offline** | Header badge changes to **Offline** (amber background) |
| **Technician scans while offline** | Scan is saved locally in the browser's IndexedDB |
| **Queue badge shows count** | Red badge appears in the header showing how many scans are queued |
| **Connection returns** | Queue is processed automatically — each queued scan is sent to the server |
| **Queue sync complete** | Badge clears, page refreshes to show updated task status |

> **No data loss:** IndexedDB persists even if the browser is closed. Queued scans survive page refresh and device restart.

### If the scanning UI doesn't load

1. Check `https://your-site/scan` is accessible — if not, your site may be down
2. Clear browser cache and reload
3. Verify the user is logged in (session may have expired)
4. Check browser console (F12) for JavaScript errors

---

## Role & Permission Matrix

### What each role can do

| Capability | Warehouse Technician | Stock User | Stock Manager | System Manager |
|---|---|---|---|---|
| **View bin locations** | ✅ Read | ✅ R/W/C | ✅ Full | — |
| **Scan putaway** | ✅ Read + Write | ✅ R/W/C | ✅ Full | — |
| **Scan pick** | ✅ Read + Write | ✅ R/W/C | ✅ Full | — |
| **View bin stock levels** | ✅ Read | ✅ Read | ✅ Read | ✅ Full |
| **View bin ledger (audit)** | ✅ Read | ✅ Read | ✅ Read | ✅ Full |
| **Access Frappe Desk** | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes |
| **Use scanning UI (/scan)** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |

### How to assign roles

1. Go to **Frappe Desk > User > [select user]**
2. Scroll to **Roles** section
3. Add the appropriate role(s) and save

> **Best practice:** Warehouse Technicians should have ONLY the **Warehouse Technician** role. This ensures they can scan but cannot accidentally edit master data or create transactions in the Desk.

---

## Technical Architecture (For IT Reference)

### Data flow diagram

```
     Purchase Receipt
          │ on_submit
          ▼
     ┌──────────────┐
     │ Putaway Task │  ← Technician scans bin
     └──────┬───────┘
            │
            ▼
     ┌──────────────────────────┐
     │ Item Batch Bin Stock     │  ← Qty increased (+)
     │ (item, batch, bin → qty) │
     └──────────────────────────┘
            │
            ▼
     ┌──────────────────────────┐
     │ Bin Stock Ledger Entry   │  ← Immutable audit trail
     └──────────────────────────┘


     Work Order / Material Request
          │ on_submit
          ▼
     ┌────────────┐
     │ Pick Task  │  ← FEFO bin suggestion
     └──────┬─────┘
            │
            ▼
     ┌──────────────────────────┐
     │ Item Batch Bin Stock     │  ← Qty decreased (-)
     └──────────────────────────┘
```

### Doctypes (database tables)

| Table | Type | Stores |
|---|---|---|
| **Bin Location** | Master | Every physical rack/bin in the warehouse |
| **Putaway Task** | Document | Receive-to-bin work orders |
| **Putaway Task Item** | Child | Individual items in a putaway task |
| **Pick Task** | Document | Pick-from-bin work orders |
| **Pick Task Item** | Child | Individual items in a pick task |
| **Bin Pick List Item** | Child | General-purpose bin pick record |
| **Item Batch Bin Stock** | Balance | Running quantity per item+batch+bin |
| **Bin Stock Ledger Entry** | Ledger | Immutable audit of every qty change |

### Key files

| File | Purpose |
|---|---|
| `hooks.py` | App config, role registration, event hook wiring |
| `api.py` | 7 whitelisted API endpoints (role-protected) |
| `utils.py` | Bin balance lookups, capacity checks |
| `www/scan.html` | Production scanning UI (Putaway / Pick / Lookup) |
| `events/purchase_receipt.py` | Auto-create Putaway Task on PR submit |
| `events/pick_list.py` | FEFO bin suggestion on Pick List validate |
| `events/work_order.py` | Auto-create Pick Task on WO submit |
| `events/material_request.py` | Auto-create Pick Task on MR submit |
| `events/stock_entry.py` | Validate and update bin ledger on Stock Entry |
| `patches/backfill_item_batch_bin_stock.py` | Go-live data migration |

### API endpoints

| Endpoint | What it does | Used by |
|---|---|---|
| `get_open_putaway_tasks` | List pending putaway tasks | Scanning UI Putaway tab |
| `get_putaway_task_detail` | Get items for a putaway task | Scanning UI (task card) |
| `scan_putaway_item` | Mark item as binned (+ capacity check) | Scanning UI scan dialog |
| `get_open_pick_tasks` | List pending pick tasks | Scanning UI Pick tab |
| `get_pick_task_detail` | Get items for a pick task | Scanning UI (task card) |
| `scan_pick_item` | Mark item as picked (bin validation) | Scanning UI scan dialog |
| `lookup_bin_stock` | Search by item/batch for all bins | Scanning UI Lookup tab |

All endpoints require a valid Frappe session AND one of: Stock Manager, Stock User, or Warehouse Technician role.

---

## Development Guide (For IT)

### Project structure

```
warehouse_binning/
├── warehouse_binning/
│   ├── hooks.py              # App config, roles, event registration
│   ├── api.py                # Whitelisted endpoints (role-gated)
│   ├── utils.py              # Core ledger + lookup functions
│   ├── patches.txt           # Migration patch registry
│   ├── patches/              # Data migration scripts
│   ├── events/               # ERPNext event hook handlers
│   ├── fixtures/             # Custom field JSON exports
│   ├── www/                  # Web-facing pages (scan.html)
│   └── doctype/              # All custom doctypes
├── .github/workflows/ci.yml
├── pyproject.toml
├── README.md
└── license.txt
```

### Adding a new doctype

```bash
bench new-doctype DoctypeName --module "Warehouse Binning"
```

Move generated files to `warehouse_binning/warehouse_binning/doctype/doctype_name/`.

### Running migrations

```bash
bench --site your-site migrate
```

---

## License

MIT
