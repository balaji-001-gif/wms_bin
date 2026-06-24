import frappe
from warehouse_binning.utils import update_bin_balance, get_available_qty

# Purposes this module enforces bin scanning on. Material Receipt is
# deliberately excluded — incoming stock is handled by the Putaway Task
# flow off Purchase Receipt, not here.
ISSUE_PURPOSES = ("Material Issue", "Material Transfer for Manufacture")


def create_pick_task_from_se(doc, method):
	"""On Stock Entry insert (Draft), create Pick Tasks for items needing
	to be picked from bins.

	Fires only for Material Issue and Material Transfer for Manufacture
	purposes. Groups items by source warehouse and suggests bins + batches
	from Item Batch Bin Stock — the technician confirms the actual pick
	via the scanning UI.

	Does not fire on Stock Entries that already have a Pick Task linked
	(via from_pick_task).
	"""
	if doc.docstatus != 0:  # Only on first Draft save
		return
	if doc.purpose not in ISSUE_PURPOSES:
		return
	if doc.from_pick_task:  # Already has a Pick Task
		return
	if doc.flags.get("skip_auto_pick_task"):  # Caller handles Pick Task creation
		return

	rows_by_warehouse = {}
	for row in doc.items:
		warehouse = row.s_warehouse
		if not warehouse:
			continue
		rows_by_warehouse.setdefault(warehouse, []).append(row)

	for warehouse, rows in rows_by_warehouse.items():
		task = frappe.new_doc("Pick Task")
		task.stock_entry = doc.name
		task.warehouse = warehouse
		task.posting_date = frappe.utils.today()
		task.status = "Pending"

		for row in rows:
			# Suggest best bin and batch from stock
			stock = frappe.db.get_value(
				"Item Batch Bin Stock",
				{"item_code": row.item_code, "warehouse": warehouse, "qty": [">", 0]},
				["bin_location", "batch_no"],
				order_by="qty desc",
				as_dict=True,
			)

			batch_no = row.batch_no or (stock.batch_no if stock else None)

			task.append("items", {
				"item_code": row.item_code,
				"batch_no": batch_no,
				"qty": row.qty,
				"uom": row.uom or frappe.db.get_value("Item", row.item_code, "stock_uom"),
				"from_bin": stock.bin_location if stock else None,
				"to_warehouse": row.t_warehouse,
				"source_row": row.name,
			})

		if task.get("items"):
			task.insert(ignore_permissions=True)
			frappe.db.set_value("Stock Entry", doc.name, "from_pick_task", task.name)


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
