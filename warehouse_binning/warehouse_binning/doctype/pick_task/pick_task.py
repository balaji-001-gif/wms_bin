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
