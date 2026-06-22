import frappe


def create_putaway_tasks(doc, method):
	"""On Purchase Receipt submit, create one Putaway Task per warehouse on
	the receipt, with one row per item+batch line. Status starts Pending —
	nothing is bin-assigned until a technician scans it.
	"""
	rows_by_warehouse = {}
	for row in doc.items:
		rows_by_warehouse.setdefault(row.warehouse, []).append(row)

	for warehouse, rows in rows_by_warehouse.items():
		task = frappe.new_doc("Putaway Task")
		task.purchase_receipt = doc.name
		task.warehouse = warehouse
		task.posting_date = doc.posting_date
		task.status = "Pending"
		for row in rows:
			task.append("items", {
				"item_code": row.item_code,
				"batch_no": row.batch_no,
				"qty": row.qty,
				"uom": row.uom,
				"source_row": row.name,
			})
		task.insert(ignore_permissions=True)
