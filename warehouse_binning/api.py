import frappe
from warehouse_binning.warehouse_binning.doctype.putaway_task.putaway_task import mark_item_scanned
from warehouse_binning.warehouse_binning.doctype.pick_task.pick_task import mark_item_picked, submit_stock_entry_for_pick_task
from warehouse_binning.utils import get_bin_stock_summary


# ---------------------------------------------------------------------------
# Session auth guard — every whitelisted endpoint checks at least one of
# these roles. The scanning UI is the primary client and uses the Frappe
# session cookie for auth. Mobile devices authenticate via the same session.
# ---------------------------------------------------------------------------

_ALLOWED_ROLES = ("Stock Manager", "Stock User", "Warehouse Technician", "System Manager")


def _require_role(user=None):
	"""Ensure the current session user has one of the allowed roles.
	Frappe's @frappe.whitelist() already requires a logged-in session;
	this adds a role gate on top.
	"""
	user = user or frappe.session.user
	if frappe.session.user == "Administrator":
		return
	roles = frappe.get_roles(user)
	if not any(r in roles for r in _ALLOWED_ROLES):
		frappe.throw(
			"You do not have permission to access this resource. "
			"A Warehouse Technician, Stock User, or Stock Manager role is required.",
			title="Insufficient Permissions",
		)


# ---------------------------------------------------------------------------
# PUTAWAY
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_open_putaway_tasks(warehouse=None):
	"""Return all non-completed Putaway Tasks, optionally filtered by warehouse."""
	_require_role()
	filters = {"status": ["!=", "Completed"]}
	if warehouse:
		filters["warehouse"] = warehouse
	return frappe.get_all(
		"Putaway Task", filters=filters, fields=["name", "warehouse", "status", "posting_date"]
	)


@frappe.whitelist()
def get_putaway_task_detail(task_name):
	"""Return a Putaway Task with its full item list for the scanning UI."""
	_require_role()
	task = frappe.get_doc("Putaway Task", task_name)
	items = []
	for row in task.items:
		items.append({
			"name": row.name,
			"item_code": row.item_code,
			"item_name": frappe.db.get_value("Item", row.item_code, "item_name"),
			"batch_no": row.batch_no,
			"qty": row.qty,
			"uom": row.uom,
			"suggested_bin": row.suggested_bin,
			"actual_bin": row.actual_bin,
			"scanned": row.scanned,
			"pending_qty": row.qty,  # after split, each row's whole qty is the pending amount
			"source_row": row.source_row,
		})
	return {
		"name": task.name,
		"warehouse": task.warehouse,
		"warehouse_name": frappe.db.get_value("Warehouse", task.warehouse, "warehouse_name"),
		"purchase_receipt": task.purchase_receipt,
		"status": task.status,
		"posting_date": task.posting_date,
		"items": items,
	}


@frappe.whitelist()
def scan_putaway_item(task_name, row_name, actual_bin, batch_no=None, qty=None):
	"""Called by the scanning UI when a technician confirms where an item
	physically landed. Supports partial qty — pass `qty` for split-row scanning.
	"""
	_require_role()
	return mark_item_scanned(task_name, row_name, actual_bin, batch_no=batch_no, qty=qty)


# ---------------------------------------------------------------------------
# PICK TASKS
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_open_pick_tasks(warehouse=None):
	"""Return all non-completed Pick Tasks, optionally filtered by warehouse."""
	_require_role()
	filters = {"status": ["!=", "Completed"]}
	if warehouse:
		filters["warehouse"] = warehouse
	return frappe.get_all(
		"Pick Task",
		filters=filters,
		fields=["name", "warehouse", "status", "posting_date", "stock_entry", "work_order", "material_request"],
		order_by="posting_date desc",
	)


@frappe.whitelist()
def get_pick_task_detail(task_name):
	"""Return a Pick Task with its full item list for the scanning UI."""
	_require_role()
	task = frappe.get_doc("Pick Task", task_name)
	items = []
	for row in task.items:
		items.append({
			"name": row.name,
			"item_code": row.item_code,
			"item_name": frappe.db.get_value("Item", row.item_code, "item_name"),
			"batch_no": row.batch_no,
			"qty": row.qty,
			"uom": row.uom,
			"from_bin": row.from_bin,
			"to_warehouse": row.to_warehouse,
			"scanned": row.scanned,
		})
	return {
		"name": task.name,
		"warehouse": task.warehouse,
		"warehouse_name": frappe.db.get_value("Warehouse", task.warehouse, "warehouse_name"),
		"stock_entry": task.stock_entry,
		"work_order": task.work_order,
		"material_request": task.material_request,
		"status": task.status,
		"posting_date": task.posting_date,
		"items": items,
	}


@frappe.whitelist()
def scan_pick_item(task_name, row_name, from_bin=None, batch_no=None):
	"""Called by the scanning UI when a technician confirms picking an item
	from a bin. Updates the task row and deduces bin stock.
	"""
	_require_role()
	return mark_item_picked(task_name, row_name, from_bin, batch_no=batch_no)


# ---------------------------------------------------------------------------
# LOOKUP / TRACEABILITY
# ---------------------------------------------------------------------------


@frappe.whitelist()
def submit_pick_task_stock_entry(task_name):
	"""Called by the scanning UI to manually trigger Stock Entry submission
	for a completed Pick Task.  Alternative to the automatic on_update hook.
	"""
	_require_role()
	return submit_stock_entry_for_pick_task(task_name)


@frappe.whitelist()
def lookup_bin_stock(item_code=None, batch_no=None, warehouse=None, bin_location=None):
	"""Traceability lookup: find where any item/batch is stored across bins.
	All parameters are optional — narrow by item_code, batch_no, warehouse,
	or bin_location.
	"""
	_require_role()
	return get_bin_stock_summary(item_code=item_code, batch_no=batch_no, warehouse=warehouse, bin_location=bin_location)
