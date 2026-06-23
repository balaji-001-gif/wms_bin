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
			"fieldname": "item_name",
			"label": _("Item Name"),
			"fieldtype": "Data",
			"width": 200,
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
			"fieldname": "suggested_bin",
			"label": _("Suggested Bin"),
			"fieldtype": "Link",
			"options": "Bin Location",
			"width": 150,
		},
		{
			"fieldname": "purchase_receipt",
			"label": _("Purchase Receipt"),
			"fieldtype": "Link",
			"options": "Purchase Receipt",
			"width": 150,
		},
	]

	conditions = ""
	if filters:
		conds = []
		if filters.get("warehouse"):
			conds.append("pt.warehouse = %(warehouse)s")
		if filters.get("item_code"):
			conds.append("pti.item_code = %(item_code)s")
		if filters.get("batch_no"):
			conds.append("pti.batch_no = %(batch_no)s")
		if conds:
			conditions = "WHERE " + " AND ".join(conds)

	data = frappe.db.sql(
		"""
		SELECT
			pt.name AS task,
			pt.status AS task_status,
			pt.warehouse,
			pti.item_code,
			COALESCE(i.item_name, '') AS item_name,
			pti.batch_no,
			pti.qty,
			pti.suggested_bin,
			pt.purchase_receipt
		FROM `tabPutaway Task Item` pti
		JOIN `tabPutaway Task` pt ON pt.name = pti.parent
		LEFT JOIN `tabItem` i ON i.name = pti.item_code
		WHERE pti.scanned = 0
			AND pt.status != 'Completed'
			{conditions}
		ORDER BY pt.name, pti.item_code
		""".format(
			conditions=conditions.replace("WHERE", "AND") if conditions else ""
		),
		filters or {},
		as_dict=True,
	)

	return columns, data
