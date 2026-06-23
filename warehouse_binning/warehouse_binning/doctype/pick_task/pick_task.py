import frappe
from frappe.model.document import Document
from warehouse_binning.utils import update_bin_balance


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
def mark_item_picked(task_name, row_name, from_bin=None):
	"""Called by the scanning UI when a technician confirms picking an item
	from a bin. Updates the task row and deduces the bin stock.
	"""
	task = frappe.get_doc("Pick Task", task_name)
	target_row = None
	for row in task.items:
		if row.name == row_name:
			row.scanned = 1
			if from_bin:
				row.from_bin = from_bin
			target_row = row
			break
	if not target_row:
		frappe.throw(f"Row {row_name} not found on {task_name}")

	task.save(ignore_permissions=True)
	frappe.db.commit()  # explicit commit — GET requests may skip auto-commit

	# Deduct from bin stock
	update_bin_balance(
		item_code=target_row.item_code,
		batch_no=target_row.batch_no,
		warehouse=task.warehouse,
		bin_location=target_row.from_bin,
		qty_change=-(target_row.qty),
		voucher_type="Pick Task",
		voucher_no=task.name,
	)
	frappe.db.commit()  # commit bin balance changes too
	return task
