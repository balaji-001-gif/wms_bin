import frappe
from frappe import _


def auto_create_stock_entry(doc, method, raise_on_error=False):
	"""On Pick Task save (on_update), if status just became 'Completed',
	find the linked Draft Stock Entry and submit it.

	The Pick Task is created from a Draft Stock Entry (via the
	create_pick_task_from_se hook in events/stock_entry.py) or from a
	Work Order (via events/work_order.py).  When the technician finishes
	scanning, this hook updates the Draft SE items with the actual batch
	and bin info from the Pick Task, creates Serial and Batch Bundles
	where needed, then submits the SE.

	When raise_on_error=True (called from the manual action button),
	exceptions propagate to the caller so the error can be shown to the
	user.  When False (called from the on_update hook), exceptions are
	caught and logged to Error Log so the scan operation completes.
	"""
	if doc.status != "Completed":
		return
	if not doc.items:
		return
	if doc.get("stock_entry_created"):
		return

	# Find the linked Draft Stock Entry
	se_name = doc.stock_entry
	if not se_name:
		# Fallback: the 'stock_entry' field on Pick Task may not exist in
		# the DB yet if 'bench migrate' hasn't been run.  Look up the SE
		# by its 'from_pick_task' custom field instead.
		se_name = frappe.db.get_value(
			"Stock Entry", {"from_pick_task": doc.name}
		)
	if not se_name:
		# When called manually, let the caller know there's no linked SE.
		if raise_on_error:
			frappe.throw(_("Pick Task {0} has no linked Stock Entry.").format(doc.name))
		return

	se = frappe.get_doc("Stock Entry", se_name)
	if se.docstatus != 0:  # Not in Draft — already submitted or cancelled
		return

	try:
		# Build a map of SE item name → SE item row for matching
		se_item_map = {}
		for se_row in se.items:
			if se_row.name:
				se_item_map[se_row.name] = se_row

		# Update SE items with batch/bin info from scanned Pick Task rows
		for row in doc.items:
			if not row.scanned:
				continue

			# Match Pick Task row to SE item by source_row (stores the
			# SE item's name from creation time)
			se_row = se_item_map.get(row.source_row)
			if not se_row:
				# Fallback: match by item_code + qty
				se_row = next(
					(r for r in se.items if r.item_code == row.item_code and r.qty == row.qty),
					None,
				)
			if not se_row:
				continue

			# Update bin location from where the technician actually picked
			if row.from_bin:
				se_row.bin_location = row.from_bin

			# For batch-tracked items: create a Serial and Batch Bundle
			# (ERPNext v15+) instead of setting batch_no directly
			if row.batch_no:
				# Keep batch_no on the item row for validation
				# (validate_bin_pick checks it) while the SBB handles
				# the actual stock ledger in v15+.
				se_row.batch_no = row.batch_no

				s_warehouse = se_row.s_warehouse
				t_warehouse = se_row.t_warehouse

				if s_warehouse and t_warehouse:
					sbb_type = "Material Transfer"
				elif s_warehouse:
					sbb_type = "Outward"
				else:
					sbb_type = "Inward"

				entry_qty = -abs(se_row.qty) if sbb_type == "Outward" else abs(se_row.qty)

				sbb = frappe.get_doc({
					"doctype": "Serial and Batch Bundle",
					"item_code": row.item_code,
					"warehouse": s_warehouse or t_warehouse,
					"company": se.company,
					"posting_date": se.posting_date or frappe.utils.today(),
					"type_of_transaction": sbb_type,
					"entries": [{
						"batch_no": row.batch_no,
						"qty": entry_qty,
					}],
				})
				sbb.insert(ignore_permissions=True)
				se_row.serial_and_batch_bundle = sbb.name

		# Save the SE with updated items
		se.flags.ignore_permissions = True
		se.save()

		# Mark on Pick Task before submit to prevent duplicates
		frappe.db.set_value("Pick Task", doc.name, "stock_entry_created", 1)
		frappe.db.commit()

		# Submit the Stock Entry
		se.flags.ignore_permissions = True
		se.submit()

		frappe.msgprint(
			_("Stock Entry {0} submitted from Pick Task {1}").format(se.name, doc.name),
			alert=True,
		)

	except Exception as e:
		frappe.log_error(
			title="Auto Stock Entry from Pick Task failed",
			message=f"Pick Task: {doc.name}, Stock Entry: {se_name}\n{str(e)}",
		)
		frappe.msgprint(
			_("Auto submit of Stock Entry {0} from Pick Task {1} failed. Check Error Log for details.").format(
				se_name, doc.name
			),
			alert=True,
			indicator="red",
		)
		# When called manually, re-raise so the caller can show the error
		if raise_on_error:
			raise
