import frappe


def execute():
	"""Backfill Item Batch Bin Stock for stock that already exists in your
	warehouses before go-live.

	Without this patch, day one has correct ERPNext qty totals but zero bin
	locations for everything already on the shelves. The bin-level pick
	suggestions (FEFO) and the Lookup view will return nothing until items
	are physically scanned into bins via Putaway Tasks — which is impossible
	for stock already sitting on racks.

	This patch creates one placeholder bin per warehouse named
	'{warehouse}-UNKNOWN' (or uses an existing one) and moves existing
	item+batch qty into it so the bin ledger is non-empty from day one.

	**After running this patch**, warehouse staff should physically audit
	each bin and move stock using Stock Transfers (or a future bin-to-bin
	transfer feature) to assign correct bin locations.

	Run with:
	  bench --site your-site console
	  >>> from warehouse_binning.warehouse_binning.patches.backfill_item_batch_bin_stock import execute
	  >>> execute()
	"""

	UNKNOWN_BIN_FLAG = "UNKNOWN"

	# Discover all warehouses that have actual stock
	warehouses_with_stock = frappe.db.sql_list(
		"""
		SELECT DISTINCT warehouse
		FROM `tabStock Ledger Entry`
		WHERE docstatus = 1
		  AND actual_qty > 0
		"""
	)

	if not warehouses_with_stock:
		frappe.log_error("No stock found to backfill.", "Warehouse Binning Backfill")
		return

	for warehouse in warehouses_with_stock:
		# Ensure a placeholder bin exists for this warehouse
		unknown_bin = f"{warehouse}-{UNKNOWN_BIN_FLAG}"
		if not frappe.db.exists("Bin Location", unknown_bin):
			frappe.get_doc({
				"doctype": "Bin Location",
				"warehouse": warehouse,
				"bin_code": UNKNOWN_BIN_FLAG,
				"is_active": 0,  # Mark inactive so it doesn't appear in normal pick suggestions
			}).insert(ignore_permissions=True)

		# Get all item + batch combos with positive qty in this warehouse
		stock_rows = frappe.db.sql(
			"""
			SELECT sle.item_code, sle.batch_no, SUM(sle.actual_qty) as qty
			FROM `tabStock Ledger Entry` sle
			WHERE sle.docstatus = 1
			  AND sle.warehouse = %s
			  AND sle.actual_qty > 0
			GROUP BY sle.item_code, sle.batch_no
			HAVING SUM(sle.actual_qty) > 0
			""",
			warehouse,
			as_dict=True,
		)

		for row in stock_rows:
			# Insert into Item Batch Bin Stock
			existing = frappe.db.get_value(
				"Item Batch Bin Stock",
				{
					"item_code": row.item_code,
					"batch_no": row.batch_no or "",
					"warehouse": warehouse,
					"bin_location": unknown_bin,
				},
				"name",
			)
			if existing:
				frappe.db.set_value("Item Batch Bin Stock", existing, "qty", row.qty)
			else:
				frappe.get_doc({
					"doctype": "Item Batch Bin Stock",
					"item_code": row.item_code,
					"batch_no": row.batch_no,
					"warehouse": warehouse,
					"bin_location": unknown_bin,
					"qty": row.qty,
				}).insert(ignore_permissions=True)

			# Also write an audit trail entry
			frappe.get_doc({
				"doctype": "Bin Stock Ledger Entry",
				"item_code": row.item_code,
				"batch_no": row.batch_no,
				"warehouse": warehouse,
				"bin_location": unknown_bin,
				"qty_change": row.qty,
				"voucher_type": "Backfill Patch",
				"voucher_no": "v0.0.1",
				"posting_datetime": frappe.utils.now_datetime(),
			}).insert(ignore_permissions=True)

	frappe.db.commit()
	frappe.log_error(
		f"Backfill complete: {len(warehouses_with_stock)} warehouse(s) processed.",
		"Warehouse Binning Backfill",
	)
