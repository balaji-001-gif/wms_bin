# Warehouse Binning

A Frappe app that adds bin/rack-level putaway and pick tracking on top of
ERPNext stock, without modifying any ERPNext source. Coupling happens only
through `doc_events` hooks (see `warehouse_binning/hooks.py`) and Custom
Field fixtures — nothing here edits erpnext's doctypes directly, so a normal
`bench update` won't conflict with it.

## What it does

- **Putaway** — submitting a Purchase Receipt auto-creates a Putaway Task
  per warehouse, one row per item+batch. A technician scans the actual bin
  for each row; that's the only thing that writes bin-level stock in.
- **Issue** — submitting a Stock Entry (Material Issue / Material Transfer
  for Manufacture) is blocked unless every row has a scanned `bin_location`
  with enough physical qty in it. Pick List rows get a suggested bin
  automatically (see caveat below).
- **Ledger** — every bin movement writes an immutable `Bin Stock Ledger
  Entry` row, then upserts the running balance in `Item Batch Bin Stock`.
  Same pattern as Frappe's own Stock Ledger Entry + Bin.

## What it does NOT do yet

Be honest with yourself about this list before you put it in front of a
warehouse floor:

- **No real FEFO.** `events/pick_list.py` suggests whichever bin has the
  most stock, not the bin with the earliest-expiring batch. If your batches
  are expiry-tracked, fix this before go-live.
- **No bin capacity checks.** Putaway will let a technician scan an item
  into a bin that's already full. There's no capacity field on `Bin
  Location` yet.
- **No real scanning UI.** `www/scan.html` is a bare unauthenticated
  placeholder that exists only to give `api.py` a visible caller. Build a
  real mobile-friendly page with barcode capture before floor use.
- **No partial-putaway UX beyond a status field.** The data model supports
  a task being half-scanned (`Partially Completed`), but there's no
  resume/queue screen for technicians to pick back up where they left off.
- **No automated tests.** The CI workflow only checks Python syntax, not
  behavior. Real coverage needs a running bench — see
  [frappe_docker](https://github.com/frappe/frappe_docker) for a CI setup
  with a real bench + MariaDB.
- **Not run against a live bench.** This was hand-authored, not generated
  by `bench new-doctype` and not migrated against a real site. Expect to
  fix small JSON/schema issues on first `bench migrate` — that's normal.

## Install

```bash
# from a local path (e.g. after unzipping this into your bench's apps dir)
bench get-app /path/to/warehouse_binning

# or once you've pushed this to your own git remote
bench get-app https://github.com/your-org/warehouse_binning --branch version-15

bench --site yoursite.local install-app warehouse_binning
bench --site yoursite.local migrate
```

Requires erpnext already installed on the site (`required_apps` in
`hooks.py` enforces this).

## Repo layout

```
warehouse_binning/
├── warehouse_binning/
│   ├── hooks.py                 # the only coupling point to erpnext
│   ├── utils.py                 # update_bin_balance() — single write path
│   ├── api.py                   # whitelisted endpoints for the scan UI
│   ├── events/                  # doc_events handlers, one file per erpnext doctype
│   ├── fixtures/                # Custom Field defs (not erpnext source edits)
│   ├── www/scan.html            # placeholder UI, see caveats above
│   └── warehouse_binning/       # module folder: doctype/ lives here
│       └── doctype/
│           ├── bin_location/
│           ├── putaway_task/
│           ├── putaway_task_item/
│           ├── bin_stock_ledger_entry/
│           └── item_batch_bin_stock/
└── .github/workflows/ci.yml
```

## Next steps, roughly in priority order

1. Run this on a real bench, fix whatever `bench migrate` complains about.
2. Decide if you need real FEFO — if yes, add `expiry_date` lookups to
   `events/pick_list.py`.
3. Add a `capacity` field to `Bin Location` and enforce it in
   `mark_item_scanned`.
4. Build the real scanning UI and lock down `api.py` with proper session
   auth for whatever device the technicians use.
5. Write a `patches.py` to backfill `Item Batch Bin Stock` for stock that
   already exists in your warehouses before go-live — otherwise day one has
   correct qty totals but unknown bin locations for everything already on
   the shelves.
