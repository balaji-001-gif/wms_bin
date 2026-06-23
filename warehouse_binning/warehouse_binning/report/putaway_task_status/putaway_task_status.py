import frappe
from frappe import _


def execute(filters=None):
	columns = [
		{
			"fieldname": "task",
			"label": _("Task"),
			"fieldtype": "Link",
			"options": "Putaway Task",
			"width": 150,
		},
		{
			"fieldname": "task_status",
			"label": _("Task Status"),
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"fieldname": "warehouse",
			"label": _("Warehouse"),
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 120,
		},
		{
			"fieldname": "item_code",
			"label": _("Item Code"),
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{
			"fieldname": "batch_no",
			"label": _("Batch No"),
			"fieldtype": "Link",
			"options": "Batch",
			"width": 120,
		},
		{
			"fieldname": "qty",
			"label": _("Qty"),
			"fieldtype": "Float",
			"width": 80,
		},
		{
			"fieldname": "item_status",
			"label": _("Item Status"),
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"fieldname": "actual_bin",
			"label": _("Actual Bin"),
			"fieldtype": "Link",
			"options": "Bin Location",
			"width": 150,
		},
		{
			"fieldname": "suggested_bin",
			"label": _("Suggested Bin"),
			"fieldtype": "Link",
			"options": "Bin Location",
			"width": 150,
		},
		{
			"fieldname": "source_row",
			"label": _("Source Row"),
			"fieldtype": "Data",
			"width": 100,
		},
	]

	conditions = ""
	if filters:
		conds = []
		if filters.get("task"):
			conds.append("pt.name = %(task)s")
		if filters.get("warehouse"):
			conds.append("pt.warehouse = %(warehouse)s")
		if filters.get("task_status"):
			conds.append("pt.status = %(task_status)s")
		if filters.get("item_status") == "Scanned":
			conds.append("pti.scanned = 1")
		elif filters.get("item_status") == "Pending":
			conds.append("pti.scanned = 0")
		if conds:
			conditions = "WHERE " + " AND ".join(conds)

	data = frappe.db.sql(
		"""
		SELECT
			pt.name AS task,
			pt.status AS task_status,
			pt.warehouse,
			pti.item_code,
			pti.batch_no,
			pti.qty,
			CASE WHEN pti.scanned = 1 THEN '✓ Scanned' ELSE 'Pending' END AS item_status,
			pti.actual_bin,
			pti.suggested_bin,
			pti.source_row
		FROM `tabPutaway Task Item` pti
		JOIN `tabPutaway Task` pt ON pt.name = pti.parent
		{conditions}
		ORDER BY pt.status, pt.name, pti.item_code
		""".format(
			conditions=conditions
		),
		filters or {},
		as_dict=True,
	)

	return columns, data
