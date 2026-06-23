import frappe
from frappe.model.document import Document


class PickTask(Document):
	def validate(self):
		self.update_status()

	def update_status(self):
		if not self.items:
			return
		if all(d.scanned for d in self.items):
			self.status = "Completed"
		elif any(d.scanned for d in self.items):
			self.status = "Partially Completed"
		else:
			self.status = "Pending"


@frappe.whitelist()
def mark_item_picked(task_name, row_name, from_bin=None, batch_no=None):
	"""Called by the scanning UI when a technician confirms picking an item
	from a bin. Updates the task row. Bin stock is deducted by the auto
	Stock Entry (created in events/pick_task.py on Pick Task completion).

	If batch_no is not provided but from_bin is, looks up the batch from
	the scanned bin's stock — this handles the common case where a barcode
	scanner fires Enter before the frontend's async auto-suggest can respond.
	"""
	task = frappe.get_doc("Pick Task", task_name)
	target_row = None
	for row in task.items:
		if row.name == row_name:
			row.scanned = 1
			if from_bin:
				row.from_bin = from_bin
			if batch_no:
				row.batch_no = batch_no
			elif from_bin and not row.batch_no:
				# Barcode scanner fired Enter before frontend auto-suggest;
				# look up the batch from the scanned bin's stock.
				existing = frappe.db.get_value(
					"Item Batch Bin Stock",
					{
						"item_code": row.item_code,
						"warehouse": task.warehouse,
						"bin_location": from_bin,
						"qty": [">", 0],
					},
					"batch_no",
					order_by="qty desc",
				)
				if existing:
					row.batch_no = existing
			target_row = row
			break
	if not target_row:
		frappe.throw(f"Row {row_name} not found on {task_name}")

	task.save(ignore_permissions=True)
	frappe.db.commit()

	# NOTE: Bin stock is NOT deducted here. The auto Stock Entry
	# (created in events/pick_task.py when the Pick Task completes)
	# handles the bin stock deduction via Stock Entry's on_submit
	# (update_bin_ledger hook). Deducting here would cause a double
	# deduction when the Stock Entry is submitted.
	return task
