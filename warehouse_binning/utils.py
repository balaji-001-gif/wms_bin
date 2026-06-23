import frappe


def update_bin_balance(item_code, batch_no, warehouse, bin_location, qty_change, voucher_type, voucher_no):
	"""Single choke point for every bin-level stock movement.

	Writes an immutable ledger row first (audit trail, never edited or
	deleted), then upserts the running balance row that the UI and pick
	suggestions actually read from. Mirrors how Frappe's own Stock Ledger
	Entry + Bin doctypes relate to each other.
	"""
	frappe.get_doc({
		"doctype": "Bin Stock Ledger Entry",
		"item_code": item_code,
		"batch_no": batch_no,
		"warehouse": warehouse,
		"bin_location": bin_location,
		"qty_change": qty_change,
		"voucher_type": voucher_type,
		"voucher_no": voucher_no,
		"posting_datetime": frappe.utils.now_datetime(),
	}).insert(ignore_permissions=True)

	existing = frappe.db.get_value(
		"Item Batch Bin Stock",
		{
			"item_code": item_code,
			"batch_no": batch_no,
			"warehouse": warehouse,
			"bin_location": bin_location,
		},
		["name", "qty"],
		as_dict=True,
	)
	if existing:
		frappe.db.set_value("Item Batch Bin Stock", existing.name, "qty", existing.qty + qty_change)
	else:
		frappe.get_doc({
			"doctype": "Item Batch Bin Stock",
			"item_code": item_code,
			"batch_no": batch_no,
			"warehouse": warehouse,
			"bin_location": bin_location,
			"qty": qty_change,
		}).insert(ignore_permissions=True)


def get_available_qty(item_code, batch_no, warehouse, bin_location):
	return frappe.db.get_value(
		"Item Batch Bin Stock",
		{
			"item_code": item_code,
			"batch_no": batch_no,
			"warehouse": warehouse,
			"bin_location": bin_location,
		},
		"qty",
	) or 0


def get_bin_stock_summary(item_code=None, batch_no=None, warehouse=None, bin_location=None):
	"""Look up stock positions across bins. Returns a list of records with
	bin_location, warehouse, batch_no, and qty. All parameters are optional
	— omit item_code to see everything (useful for warehouse-wide views).
	"""
	filters = {}
	if item_code:
		filters["item_code"] = item_code
	if batch_no:
		filters["batch_no"] = batch_no
	if warehouse:
		filters["warehouse"] = warehouse
	if bin_location:
		filters["bin_location"] = bin_location

	return frappe.get_all(
		"Item Batch Bin Stock",
		filters=filters,
		fields=["item_code", "batch_no", "warehouse", "bin_location", "qty"],
		order_by="bin_location asc",
	)


def get_bin_current_usage(bin_location, warehouse):
	"""Return the total qty currently stored in a bin across all items/batches."""
	result = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(qty), 0)
		FROM `tabItem Batch Bin Stock`
		WHERE bin_location = %s AND warehouse = %s
		""",
		(bin_location, warehouse),
	)
	return result[0][0] if result else 0


def get_bin_capacity(bin_location):
	"""Return the capacity of a bin location, or None if not set."""
	return frappe.db.get_value("Bin Location", bin_location, "capacity")


def get_barcode_svg(value, barcode_type="code128", height=30):
	"""Generate a barcode SVG string for use in print formats.

	Uses the python-barcode library (Code128 by default). Returns an
	inline SVG element as a string, safe to embed in HTML print formats.

	Args:
		value: The data to encode (e.g. bin location name, item code).
		barcode_type: Symbology (code128, ean13, qr, etc.)
		height: Height of the barcode in pixels.

	Returns:
		str: SVG markup for the barcode, or empty string on failure.
	"""
	if not value:
		return ""
	try:
		from io import BytesIO

		import barcode
		from barcode.writer import SVGWriter

		writer = SVGWriter()
		writer.set_options({
			"module_height": height / 60.0 if height else 0.5,
			"module_width": 0.25,
			"font_size": 1,
			"text_distance": 0,
			"quiet_zone": 2,
			"write_text": False,
			"background": "white",
			"foreground": "black",
		})

		code = barcode.get(barcode_type, value, writer=writer)
		buf = BytesIO()
		code.write(buf)
		return buf.getvalue().decode("utf-8")
	except Exception:
		frappe.log_error(f"Barcode generation failed for {value}", "Warehouse Binning")
		return f"<!-- barcode failed for {value} -->"
