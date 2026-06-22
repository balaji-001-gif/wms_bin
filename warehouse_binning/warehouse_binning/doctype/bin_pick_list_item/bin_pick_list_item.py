from frappe.model.document import Document


class BinPickListItem(Document):
	"""Records a single bin-level pick action — which item+batch was picked
	from which bin, in what quantity, and for which source document.

	This is an istable (child table) doctype intended to be embedded in
	any document that needs to record bin-level pick details: Pick Tasks,
	Stock Entries, or a future Bin Pick List summary document.
	"""
	pass
