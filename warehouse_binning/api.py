import frappe
from warehouse_binning.warehouse_binning.doctype.putaway_task.putaway_task import mark_item_scanned
from warehouse_binning.warehouse_binning.doctype.pick_task.pick_task import mark_item_picked
from warehouse_binning.utils import get_bin_stock_summary


# ---------------------------------------------------------------------------
# PUTAWAY
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_open_putaway_tasks(warehouse=None):
	"""Return all non-completed Putaway Tasks, optionally filtered by warehouse."""
	filters = {"status": ["!=", "Completed"]}
	if warehouse:
		filters["warehouse"] = warehouse
	return frappe.get_all(
		"Putaway Task", filters=filters, fields=["name", "warehouse", "status", "posting_date"]
	)


@frappe.whitelist()
def get_putaway_task_detail(task_name):
	"""Return a Putaway Task with its full item list for the scanning UI."""
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
def scan_putaway_item(task_name, row_name, actual_bin, batch_no=None):
	"""Called by the scanning UI when a technician confirms where an item
	physically landed. Updates the task row, then writes the bin-level
	stock movement.
	"""
	return mark_item_scanned(task_name, row_name, actual_bin, batch_no)


# ---------------------------------------------------------------------------
# PICK TASKS
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_open_pick_tasks(warehouse=None):
	"""Return all non-completed Pick Tasks, optionally filtered by warehouse."""
	filters = {"status": ["!=", "Completed"]}
	if warehouse:
		filters["warehouse"] = warehouse
	return frappe.get_all(
		"Pick Task",
		filters=filters,
		fields=["name", "warehouse", "status", "posting_date", "work_order", "material_request"],
		order_by="posting_date desc",
	)


@frappe.whitelist()
def get_pick_task_detail(task_name):
	"""Return a Pick Task with its full item list for the scanning UI."""
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
		"work_order": task.work_order,
		"material_request": task.material_request,
		"status": task.status,
		"posting_date": task.posting_date,
		"items": items,
	}


@frappe.whitelist()
def scan_pick_item(task_name, row_name, from_bin=None):
	"""Called by the scanning UI when a technician confirms picking an item
	from a bin. Updates the task row and deduces bin stock.
	"""
	return mark_item_picked(task_name, row_name, from_bin)


# ---------------------------------------------------------------------------
# LOOKUP / TRACEABILITY
# ---------------------------------------------------------------------------


@frappe.whitelist()
def lookup_bin_stock(item_code=None, batch_no=None, warehouse=None):
	"""Traceability lookup: find where any item/batch is stored across bins.
	All parameters are optional — narrow by item_code, batch_no, or warehouse.
	"""
	return get_bin_stock_summary(item_code=item_code, batch_no=batch_no, warehouse=warehouse)
