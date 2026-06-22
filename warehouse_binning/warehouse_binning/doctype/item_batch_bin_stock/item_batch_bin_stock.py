from frappe.model.document import Document


class ItemBatchBinStock(Document):
	# Upserted only via warehouse_binning.utils.update_bin_balance.
	# There is no DB-level unique constraint on
	# (item_code, batch_no, warehouse, bin_location) here — the upsert
	# logic in update_bin_balance is what prevents duplicate balance rows.
	# If you ever write to this doctype from anywhere else, you will get
	# duplicate balances for the same bin.
	pass
