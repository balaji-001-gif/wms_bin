# Warehouse Binning

Bin-level putaway and pick tracking layered on top of ERPNext stock. Tracks every item+batch to a specific rack/bin location — so any technician can find material without searching the warehouse.

## Features

- **Putaway (Receive-to-Bin)**: After a Purchase Receipt is submitted, a Putaway Task is created automatically. A technician scans items into specific bin locations using the mobile scanning UI.
- **Pick (Issue-from-Bin)**: When a Work Order or Material Request is submitted, a Pick Task is created with bin suggestions (FEFO — First-Expiry-First-Out). The technician picks from the suggested bin and confirms with a scan.
- **Traceability**: Look up any item or batch to see exactly which bins hold stock and in what quantity.
- **Offline Support**: Scans are queued locally via IndexedDB when offline and auto-synced when connectivity returns.
- **FEFO**: Pick suggestions prioritize the earliest-expiring batch first, then the bin with the most stock.
- **Mobile Scanning UI**: Mobile-first web interface with large touch targets, barcode scanner support, and 3 views (Putaway / Pick / Lookup).

## Requirements

- ERPNext v15 (or later)
- Frappe Framework v15 (or later)
- Python 3.10+
- Node.js 18+ (for asset building)

## Installation

### 1. Install the app on your Frappe site

```bash
bench get-app https://github.com/your-org/warehouse_binning
bench --site your-site install-app warehouse_binning
bench --site your-site migrate
```

The `migrate` step creates the **Warehouse Technician** role and installs custom fields on ERPNext's own doctypes (Pick List Item, Stock Entry Detail).

### 2. Set up bin locations

Before scanning, you need bin locations set up. Create them in the Frappe Desk:

1. Go to **Warehouse Binning > Bin Location**
2. Create one entry per rack/bin using the format: `{Warehouse}-{BinCode}`
3. Set Zone and Rack for visual grouping

Or use the API:
```python
import frappe
bin_loc = frappe.get_doc({
    "doctype": "Bin Location",
    "warehouse": "Stores - W",
    "zone": "A",
    "rack": "A-01",
    "bin_code": "A-01-001"
}).insert()
```

### 3. Assign role to technicians

1. Go to **User > [Technician User] > Roles**
2. Add **Warehouse Technician** role
3. No Desk access needed — technicians use the scanning UI only

The **Warehouse Technician** role has:
- Read/Write: Putaway Tasks, Pick Tasks
- Read: Bin Locations, Item Batch Bin Stock, Bin Stock Ledger Entry
- No: Delete or Desk access

## Configuration

### Custom Fields

The app installs a `bin_location` (Link → Bin Location) field on:
- **Pick List Item** — set automatically via FEFO suggestion
- **Stock Entry Detail** — used for bin validation on submit

No additional configuration is needed.

### Event Hooks (automatic)

| Trigger | Action |
|---|---|
| Purchase Receipt submitted | Creates Putaway Tasks (one per warehouse) |
| Work Order submitted | Creates Pick Tasks for required materials |
| Material Request submitted | Creates Pick Tasks (Material Issue type only) |
| Stock Entry validating | Validates bin quantity before submit |
| Stock Entry submitted | Deducts from bin ledger |
| Stock Entry cancelled | Reverses bin ledger deduction |
| Pick List validating | Suggests FEFO bin (earliest expiry first) |

## Usage

### Scanning UI

Access the scanning UI at:

```
https://your-site/scan
```

The interface has 3 tabs at the bottom:

#### 📥 Putaway View

1. Open tasks appear automatically
2. Tap a task card to expand its items
3. Tap **Scan Bin** on an unscanned item
4. Scan or type the bin barcode → **Confirm**
5. Item is recorded and bin stock is updated
6. Progress bar shows completion

#### 📤 Pick View

1. Open pick tasks appear (auto-created from Work Orders / Material Requests)
2. Filter by warehouse using the search bar
3. Tap a task card to expand items with suggested bins
4. Tap **Pick** on an item
5. Scan the bin barcode → system validates it matches the suggested bin
6. Bin stock is deducted
7. Progress bar shows completion

#### 🔍 Lookup View

1. Scan or type an item code or batch number
2. Summary cards show total quantity, bin count, and entries
3. Table lists every bin with stock for that item/batch

### Offline Mode

When the device is offline:
1. A **Offline** badge appears in the header
2. Scan actions are queued locally (IndexedDB)
3. A red badge shows the queue count
4. When connection restores, the queue auto-syncs
5. Synced tasks are automatically refreshed

## Architecture

### Data Flow

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
                    │  (Pending)       │
                    └────────┬─────────┘
                             │ Technician picks from bin
                             ▼
                    ┌──────────────────┐
                    │  Item Batch Bin  │ ← Stock deducted (-qty)
                    │  Stock           │
                    └──────────────────┘
```

### Doctypes

| Doctype | Type | Purpose |
|---|---|---|
| Bin Location | Master | Physical rack/bin locations |
| Putaway Task | Document | Receive-to-bin task |
| Putaway Task Item | Child Table | Items within a putaway task |
| Pick Task | Document | Pick-from-bin task |
| Pick Task Item | Child Table | Items within a pick task |
| Bin Pick List Item | Child Table | General-purpose bin pick record |
| Item Batch Bin Stock | Document | Running balance at (item, batch, warehouse, bin) |
| Bin Stock Ledger Entry | Document | Immutable audit trail |

### Key Files

| File | Purpose |
|---|---|
| `hooks.py` | App config, role definitions, event hook registration |
| `api.py` | 9 whitelisted API endpoints for the scanning UI |
| `utils.py` | Core ledger functions: `update_bin_balance`, `get_available_qty`, `get_bin_stock_summary` |
| `www/scan.html` | Mobile scanning UI (single-page app, 3 views + offline queue) |
| `events/purchase_receipt.py` | Creates Putaway Tasks on PR submit |
| `events/stock_entry.py` | Validates bin qty, updates/reverses ledger |
| `events/pick_list.py` | FEFO bin suggestion on Pick List validate |
| `events/work_order.py` | Creates Pick Tasks from Work Order required items |
| `events/material_request.py` | Creates Pick Tasks from Material Issue requests |
| `fixtures/custom_field.json` | Custom fields on ERPNext doctypes |

## Development

### Project structure

```
warehouse_binning/
├── warehouse_binning/
│   ├── hooks.py, api.py, utils.py, patches.txt
│   ├── events/            # ERPNext event handlers
│   ├── fixtures/          # Custom field exports
│   ├── www/               # Web-facing pages (scan.html)
│   └── doctype/           # All custom doctypes
└── pyproject.toml
```

### Adding a new doctype

```bash
bench new-doctype DoctypeName --module "Warehouse Binning"
```

Move the generated files to `warehouse_binning/warehouse_binning/doctype/doctype_name/`.

### Running migrations after changes

```bash
bench --site your-site migrate
```

## License

MIT
