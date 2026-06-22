import frappe


def create_pick_tasks(doc, method):
	"""On Work Order submit, create Pick Tasks for all required materials.

	Groups required items by source warehouse and creates one Pick Task
	per warehouse with suggested bins from Item Batch Bin Stock.
	"""
	if doc.status not in ("Planned", "Material Requested"):
		return

	rows_by_warehouse = {}
	for row in doc.required_items:
		warehouse = row.source_warehouse or doc.fg_warehouse
		if not warehouse:
			continue
		rows_by_warehouse.setdefault(warehouse, []).append(row)

	for warehouse, rows in rows_by_warehouse.items():
		task = frappe.new_doc("Pick Task")
		task.work_order = doc.name
		task.warehouse = warehouse
		task.posting_date = doc.planned_start_date or frappe.utils.today()
		task.status = "Pending"

		for row in rows:
			# Suggest best bin + batch from Item Batch Bin Stock
			stock = frappe.db.get_value(
				"Item Batch Bin Stock",
				{"item_code": row.item_code, "warehouse": warehouse, "qty": [">", 0]},
				["bin_location", "batch_no"],
				order_by="qty desc",
				as_dict=True,
			)

			task.append("items", {
				"item_code": row.item_code,
				"batch_no": stock.batch_no if stock else None,
				"qty": row.required_qty,
				"uom": frappe.db.get_value("Item", row.item_code, "stock_uom"),
				"from_bin": stock.bin_location if stock else None,
				"to_warehouse": doc.fg_warehouse,
				"source_row": row.name,
			})

		if task.get("items"):
			task.insert(ignore_permissions=True)
