import frappe
from frappe import _


def execute(filters=None):
	columns = [
		{
			"fieldname": "warehouse",
			"label": _("Warehouse"),
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 150,
		},
		{
			"fieldname": "bin_location",
			"label": _("Bin Location"),
			"fieldtype": "Link",
			"options": "Bin Location",
			"width": 200,
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
			"width": 150,
		},
		{
			"fieldname": "qty",
			"label": _("Quantity"),
			"fieldtype": "Float",
			"width": 100,
		},
	]

	data = frappe.db.sql(
		"""
		SELECT
			ibbs.warehouse,
			ibbs.bin_location,
			ibbs.item_code,
			COALESCE(i.item_name, '') AS item_name,
			ibbs.batch_no,
			ibbs.qty
		FROM `tabItem Batch Bin Stock` ibbs
		LEFT JOIN `tabItem` i ON i.name = ibbs.item_code
		{conditions}
		ORDER BY ibbs.warehouse, ibbs.bin_location, ibbs.item_code
		""".format(
			conditions=_get_conditions(filters)
		),
		filters or {},
		as_dict=True,
	)

	return columns, data


def _get_conditions(filters):
	conditions = []
	if filters:
		if filters.get("warehouse"):
			conditions.append("ibbs.warehouse = %(warehouse)s")
		if filters.get("bin_location"):
			conditions.append("ibbs.bin_location = %(bin_location)s")
		if filters.get("item_code"):
			conditions.append("ibbs.item_code = %(item_code)s")
		if filters.get("batch_no"):
			conditions.append("ibbs.batch_no = %(batch_no)s")
	if conditions:
		return "WHERE " + " AND ".join(conditions)
	return ""
