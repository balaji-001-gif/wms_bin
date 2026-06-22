import frappe
from warehouse_binning.utils import update_bin_balance, get_available_qty

# Purposes this module enforces bin scanning on. Material Receipt is
# deliberately excluded — incoming stock is handled by the Putaway Task
# flow off Purchase Receipt, not here.
ISSUE_PURPOSES = ("Material Issue", "Material Transfer for Manufacture")


def validate_bin_pick(doc, method):
	"""Before submit: every issue/transfer row needs a confirmed bin with
	enough physical qty in it. This is the enforcement point — if you skip
	this hook, technicians can submit against whatever the system suggested
	without ever actually scanning, and your bin ledger silently goes stale.
	"""
	if doc.purpose not in ISSUE_PURPOSES:
		return
	for row in doc.items:
		bin_location = row.get("bin_location")
		if not bin_location:
			frappe.throw(f"Row {row.idx}: no bin location scanned for {row.item_code}")
		available = get_available_qty(row.item_code, row.batch_no, row.s_warehouse, bin_location)
		if available < row.qty:
			frappe.throw(
				f"Row {row.idx}: bin {bin_location} only has {available} of "
				f"{row.item_code}, batch {row.batch_no}, but {row.qty} is needed"
			)


def update_bin_ledger(doc, method):
	if doc.purpose not in ISSUE_PURPOSES:
		return
	for row in doc.items:
		bin_location = row.get("bin_location")
		if not bin_location:
			continue
		update_bin_balance(
			item_code=row.item_code,
			batch_no=row.batch_no,
			warehouse=row.s_warehouse,
			bin_location=bin_location,
			qty_change=-row.qty,
			voucher_type="Stock Entry",
			voucher_no=doc.name,
		)


def reverse_bin_ledger(doc, method):
	if doc.purpose not in ISSUE_PURPOSES:
		return
	for row in doc.items:
		bin_location = row.get("bin_location")
		if not bin_location:
			continue
		update_bin_balance(
			item_code=row.item_code,
			batch_no=row.batch_no,
			warehouse=row.s_warehouse,
			bin_location=bin_location,
			qty_change=row.qty,
			voucher_type="Stock Entry",
			voucher_no=doc.name,
		)
