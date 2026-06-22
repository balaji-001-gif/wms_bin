from frappe.model.document import Document


class BinStockLedgerEntry(Document):
	# Written only via warehouse_binning.utils.update_bin_balance.
	# Treat rows as immutable: never edit qty_change after insert, only
	# insert a reversing entry (see events/stock_entry.py on_cancel).
	pass
