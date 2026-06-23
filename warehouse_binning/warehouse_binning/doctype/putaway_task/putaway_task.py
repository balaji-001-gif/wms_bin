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
def mark_item_scanned(task_name, row_name, actual_bin, batch_no=None, qty=None):
	"""Called by the scanning UI when a technician confirms where an item
	physically landed. Updates the task row, then writes the bin-level
	stock movement — this is the only place incoming putaway qty enters
	Item Batch Bin Stock.

	Supports partial qty scanning: if `qty` is less than the row's total
	qty, the row is split. The scanned portion is marked complete and
	moved to the bin; the remainder stays in a new row for later scanning.

	Enforces bin capacity: if the bin has a capacity set, the total
	quantity after adding this item must not exceed it.
	"""
	task = frappe.get_doc("Putaway Task", task_name)

	# Find the target row and validate
	target_row = None
	row_index = -1
	for i, row in enumerate(task.items):
		if row.name == row_name:
			target_row = row
			row_index = i
			break
	if not target_row:
		frappe.throw(f"Row {row_name} not found on {task_name}")

	# Determine how much to scan
	scan_qty = float(qty) if qty is not None else float(target_row.qty)
	remaining_qty = float(target_row.qty) - scan_qty

	if scan_qty <= 0:
		frappe.throw("Scan qty must be greater than zero.")
	if scan_qty > float(target_row.qty):
		frappe.throw(
			f"Scan qty ({scan_qty}) exceeds row qty ({target_row.qty})."
		)

	# --- Capacity check ---
	capacity = get_bin_capacity(actual_bin)
	if capacity is not None and capacity > 0:
		current_usage = get_bin_current_usage(actual_bin, task.warehouse)
		if current_usage + scan_qty > capacity:
			frappe.throw(
				f"Bin {actual_bin} capacity ({capacity}) would be exceeded. "
				f"Current usage: {current_usage}, trying to add: {scan_qty}."
			)

	# If partial scan: split the row
	is_partial = remaining_qty > 0

	if is_partial:
		# Insert a new row with the remaining qty (insert after current row)
		new_row = frappe.copy_doc(target_row, ignore_no_copy=False)
		new_row.name = None  # clear name so Frappe generates a fresh one
		new_row.qty = remaining_qty
		new_row.actual_bin = None
		new_row.scanned = 0
		new_row.source_row = target_row.name
		task.items.insert(row_index + 1, new_row)

		# Reduce current row to the scanned qty and mark scanned
		target_row.qty = scan_qty
	else:
		# Full scan - just mark scanned
		target_row.scanned = 1

	target_row.actual_bin = actual_bin
	target_row.scanned = 1
	if batch_no:
		target_row.batch_no = batch_no

	task.save(ignore_permissions=True)
	frappe.db.commit()  # explicit commit — GET requests may skip auto-commit

	update_bin_balance(
		item_code=target_row.item_code,
		batch_no=target_row.batch_no,
		warehouse=task.warehouse,
		bin_location=target_row.actual_bin,
		qty_change=scan_qty,
		voucher_type="Putaway Task",
		voucher_no=task.name,
	)
	frappe.db.commit()  # commit bin balance changes too
	return task
