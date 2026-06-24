import frappe


def create_pick_tasks(doc, method):
	"""On Work Order submit, create a Draft Stock Entry and a Pick Task
	for the required materials.

	The Draft Stock Entry is inserted first, then the Pick Task is created
	with both stock_entry and work_order references.  When the technician
	finishes scanning, the Pick Task's on_update hook submits the Draft SE.

	This replaces the old flow where Pick Tasks were created directly from
	the Work Order without a Draft SE.  Now all issue/transfer flows go
	through a common Stock Entry → Pick Task → submit Stock Entry pipeline.
	"""
	if doc.status not in ("Planned", "Material Requested"):
		return

	# Group required items by source warehouse
	rows_by_warehouse = {}
	for row in doc.required_items:
		warehouse = row.source_warehouse or doc.fg_warehouse
		if not warehouse:
			continue
		rows_by_warehouse.setdefault(warehouse, []).append(row)

	# Create one Stock Entry + Pick Task per warehouse group
	for warehouse, rows in rows_by_warehouse.items():
		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = "Material Transfer for Manufacture"
		se.purpose = "Material Transfer for Manufacture"
		se.posting_date = doc.planned_start_date or frappe.utils.today()
		se.company = frappe.db.get_value(
			"Warehouse", warehouse, "company"
		) or frappe.defaults.get_company_default("company")

		for row in rows:
			stock_uom = frappe.db.get_value("Item", row.item_code, "stock_uom")

			se.append("items", {
				"item_code": row.item_code,
				"qty": row.required_qty,
				"s_warehouse": warehouse,
				"t_warehouse": doc.fg_warehouse,
				"uom": stock_uom,
				"stock_uom": stock_uom,
				"conversion_factor": 1,
			})

		if not se.get("items"):
			continue

		# Set flag to prevent the SE after_insert hook from creating a
		# duplicate Pick Task — the WO handler creates it directly below
		# with both stock_entry and work_order references.
		se.flags.skip_auto_pick_task = True
		se.insert(ignore_permissions=True)

		# Create the Pick Task directly (setting both stock_entry and
		# work_order so the scanning UI can show the WO reference)
		task = frappe.new_doc("Pick Task")
		task.stock_entry = se.name
		task.work_order = doc.name
		task.warehouse = warehouse
		task.posting_date = doc.planned_start_date or frappe.utils.today()
		task.status = "Pending"

		for row in rows:
			# Suggest best bin and batch from Item Batch Bin Stock
			stock = frappe.db.get_value(
				"Item Batch Bin Stock",
				{"item_code": row.item_code, "warehouse": warehouse, "qty": [">", 0]},
				["bin_location", "batch_no"],
				order_by="qty desc",
				as_dict=True,
			)

			stock_uom = frappe.db.get_value("Item", row.item_code, "stock_uom")

			task.append("items", {
				"item_code": row.item_code,
				"batch_no": stock.batch_no if stock else None,
				"qty": row.required_qty,
				"uom": stock_uom,
				"from_bin": stock.bin_location if stock else None,
				"to_warehouse": doc.fg_warehouse,
				"source_row": row.name,
			})

		if task.get("items"):
			task.insert(ignore_permissions=True)
			# Link SE back to Pick Task
			frappe.db.set_value("Stock Entry", se.name, "from_pick_task", task.name)
