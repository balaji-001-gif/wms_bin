import frappe


def create_pick_tasks(doc, method):
	"""On Material Request submit, create Pick Tasks for items needing to
	be issued from stores.

	Only fires for Material Issue type requests. Groups by source
	warehouse and suggests bins from Item Batch Bin Stock.
	"""
	if doc.material_request_type != "Material Issue":
		return

	rows_by_warehouse = {}
	for row in doc.items:
		warehouse = row.warehouse
		if not warehouse:
			continue
		rows_by_warehouse.setdefault(warehouse, []).append(row)

	for warehouse, rows in rows_by_warehouse.items():
		task = frappe.new_doc("Pick Task")
		task.material_request = doc.name
		task.warehouse = warehouse
		task.posting_date = frappe.utils.today()
		task.status = "Pending"

		for row in rows:
			# Suggest best bin
			suggested_bin = frappe.db.get_value(
				"Item Batch Bin Stock",
				{"item_code": row.item_code, "warehouse": warehouse, "qty": [">", 0]},
				"bin_location",
				order_by="qty desc",
			)

			task.append("items", {
				"item_code": row.item_code,
				"batch_no": getattr(row, "batch_no", None),
				"qty": row.qty,
				"uom": row.uom,
				"from_bin": suggested_bin,
				"to_warehouse": warehouse,
				"source_row": row.name,
			})

		if task.get("items"):
			task.insert(ignore_permissions=True)
