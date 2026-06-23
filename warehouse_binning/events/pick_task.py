import frappe
from frappe import _


def auto_create_stock_entry(doc, method):
	"""On Pick Task save (on_update), if status just became 'Completed' and no
	Stock Entry has been created yet, auto-generate and submit one.

	For Pick Tasks linked to a Material Request → creates a Material Issue SE.
	For Pick Tasks linked to a Work Order → creates a Material Transfer for
	Manufacture SE.  This automates the "pick from bins → issue to production
	or to the requesting party" workflow so floor staff never need to touch the
	Desk after scanning.
	"""
	if doc.status != "Completed":
		return
	if doc.get("stock_entry_created"):
		return
	if not doc.items:
		return

	# Determine Stock Entry purpose
	if doc.material_request:
		purpose = "Material Issue"
	elif doc.work_order:
		purpose = "Material Transfer for Manufacture"
	else:
		return

	try:
		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = purpose
		se.from_pick_task = doc.name
		se.purpose = purpose
		se.posting_date = frappe.utils.today()
		se.company = frappe.db.get_value(
			"Warehouse", doc.warehouse, "company"
		) or frappe.defaults.get_company_default("company")

		for row in doc.items:
			if not row.scanned:
				continue
			s_warehouse = doc.warehouse
			t_warehouse = row.to_warehouse if purpose == "Material Transfer for Manufacture" else None

			se.append("items", {
				"item_code": row.item_code,
				"batch_no": row.batch_no,
				"qty": row.qty,
				"s_warehouse": s_warehouse,
				"t_warehouse": t_warehouse,
				"bin_location": row.from_bin,
				"uom": row.uom,
				"stock_uom": row.uom or frappe.db.get_value("Item", row.item_code, "stock_uom"),
				"conversion_factor": 1,
			})

		se.insert(ignore_permissions=True)

		# Mark immediately (before submit) to prevent duplicate Stock Entries
		# if submit fails for any reason.
		frappe.db.set_value("Pick Task", doc.name, "stock_entry_created", 1)
		frappe.db.commit()

		# Submit with ignore_permissions — Warehouse Technicians who trigger
		# this hook via scanning may not have explicit Submit permission on
		# Stock Entry.
		se.flags.ignore_permissions = True
		se.submit()

		frappe.msgprint(
			_("Stock Entry {0} created and submitted from Pick Task {1}").format(
				se.name, doc.name
			),
			alert=True,
		)

	except Exception as e:
		frappe.log_error(
			title="Auto Stock Entry from Pick Task failed",
			message=f"Pick Task: {doc.name}\n{str(e)}",
		)
		frappe.msgprint(
			_("Auto Stock Entry from Pick Task {0} failed. Check Error Log for details.").format(
				doc.name
			),
			alert=True,
			indicator="red",
		)
