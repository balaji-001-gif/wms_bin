import frappe
from frappe.model.document import Document
from warehouse_binning.utils import (
	update_bin_balance,
	get_bin_current_usage,
	get_bin_capacity,
)


class PutawayTask(Document):
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
def mark_item_scanned(task_name, row_name, actual_bin, batch_no=None):
	"""Called by the scanning UI when a technician confirms where an item
	physically landed. Updates the task row, then writes the bin-level
	stock movement — this is the only place incoming putaway qty enters
	Item Batch Bin Stock.

	Enforces bin capacity: if the bin has a capacity set, the total
	quantity after adding this item must not exceed it.
	"""
	task = frappe.get_doc("Putaway Task", task_name)

	# --- Capacity check ---
	capacity = get_bin_capacity(actual_bin)
	if capacity is not None and capacity > 0:
		current_usage = get_bin_current_usage(actual_bin, task.warehouse)
		for row in task.items:
			if row.name == row_name:
				added_qty = row.qty
				if current_usage + added_qty > capacity:
					frappe.throw(
						f"Bin {actual_bin} capacity ({capacity}) would be exceeded. "
						f"Current usage: {current_usage}, trying to add: {added_qty}."
					)
				break

	target_row = None
	for row in task.items:
		if row.name == row_name:
			row.actual_bin = actual_bin
			row.scanned = 1
			if batch_no:
				row.batch_no = batch_no
			target_row = row
			break
	if not target_row:
		frappe.throw(f"Row {row_name} not found on {task_name}")

	task.save(ignore_permissions=True)

	update_bin_balance(
		item_code=target_row.item_code,
		batch_no=target_row.batch_no,
		warehouse=task.warehouse,
		bin_location=target_row.actual_bin,
		qty_change=target_row.qty,
		voucher_type="Putaway Task",
		voucher_no=task.name,
	)
	return task
