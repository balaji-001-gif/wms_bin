import frappe
from frappe import _


def execute(filters=None):
	columns = [
		{
			"fieldname": "posting_datetime",
			"label": _("Date/Time"),
			"fieldtype": "Datetime",
			"width": 160,
		},
		{
			"fieldname": "voucher_type",
			"label": _("Voucher Type"),
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"fieldname": "voucher_no",
			"label": _("Voucher No"),
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 150,
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
			"fieldname": "warehouse",
			"label": _("Warehouse"),
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 120,
		},
		{
			"fieldname": "bin_location",
			"label": _("Bin Location"),
			"fieldtype": "Link",
			"options": "Bin Location",
			"width": 150,
		},
		{
			"fieldname": "qty_change",
			"label": _("Qty Change"),
			"fieldtype": "Float",
			"width": 100,
		},
	]

	conditions = ""
	if filters:
		conds = []
		if filters.get("item_code"):
			conds.append("bsle.item_code = %(item_code)s")
		if filters.get("batch_no"):
			conds.append("bsle.batch_no = %(batch_no)s")
		if filters.get("warehouse"):
			conds.append("bsle.warehouse = %(warehouse)s")
		if filters.get("bin_location"):
			conds.append("bsle.bin_location = %(bin_location)s")
		if filters.get("from_date"):
			conds.append("bsle.posting_datetime >= %(from_date)s")
		if filters.get("to_date"):
			conds.append("bsle.posting_datetime <= %(to_date)s")
		if conds:
			conditions = "WHERE " + " AND ".join(conds)

	data = frappe.db.sql(
		"""
		SELECT
			bsle.posting_datetime,
			bsle.voucher_type,
			bsle.voucher_no,
			bsle.item_code,
			bsle.batch_no,
			bsle.warehouse,
			bsle.bin_location,
			bsle.qty_change
		FROM `tabBin Stock Ledger Entry` bsle
		{conditions}
		ORDER BY bsle.posting_datetime DESC
		""".format(
			conditions=conditions
		),
		filters or {},
		as_dict=True,
	)

	return columns, data
