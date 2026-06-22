import frappe


def update_bin_balance(item_code, batch_no, warehouse, bin_location, qty_change, voucher_type, voucher_no):
	"""Single choke point for every bin-level stock movement.

	Writes an immutable ledger row first (audit trail, never edited or
	deleted), then upserts the running balance row that the UI and pick
	suggestions actually read from. Mirrors how Frappe's own Stock Ledger
	Entry + Bin doctypes relate to each other.
	"""
	frappe.get_doc({
		"doctype": "Bin Stock Ledger Entry",
		"item_code": item_code,
		"batch_no": batch_no,
		"warehouse": warehouse,
		"bin_location": bin_location,
		"qty_change": qty_change,
		"voucher_type": voucher_type,
		"voucher_no": voucher_no,
		"posting_datetime": frappe.utils.now_datetime(),
	}).insert(ignore_permissions=True)

	existing = frappe.db.get_value(
		"Item Batch Bin Stock",
		{
			"item_code": item_code,
			"batch_no": batch_no,
			"warehouse": warehouse,
			"bin_location": bin_location,
		},
		["name", "qty"],
		as_dict=True,
	)
	if existing:
		frappe.db.set_value("Item Batch Bin Stock", existing.name, "qty", existing.qty + qty_change)
	else:
		frappe.get_doc({
			"doctype": "Item Batch Bin Stock",
			"item_code": item_code,
			"batch_no": batch_no,
			"warehouse": warehouse,
			"bin_location": bin_location,
			"qty": qty_change,
		}).insert(ignore_permissions=True)


def get_available_qty(item_code, batch_no, warehouse, bin_location):
	return frappe.db.get_value(
		"Item Batch Bin Stock",
		{
			"item_code": item_code,
			"batch_no": batch_no,
			"warehouse": warehouse,
			"bin_location": bin_location,
		},
		"qty",
	) or 0


def get_bin_stock_summary(item_code=None, batch_no=None, warehouse=None):
	"""Look up stock positions across bins. Returns a list of records with
	bin_location, warehouse, batch_no, and qty. All parameters are optional
	— omit item_code to see everything (useful for warehouse-wide views).
	"""
	filters = {}
	if item_code:
		filters["item_code"] = item_code
	if batch_no:
		filters["batch_no"] = batch_no
	if warehouse:
		filters["warehouse"] = warehouse

	return frappe.get_all(
		"Item Batch Bin Stock",
		filters=filters,
		fields=["item_code", "batch_no", "warehouse", "bin_location", "qty"],
		order_by="bin_location asc",
	)
