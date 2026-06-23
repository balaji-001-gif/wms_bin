app_name = "warehouse_binning"
app_title = "Warehouse Binning"
app_publisher = "Your Company"
app_description = "Bin-level putaway and pick tracking layered on top of ERPNext stock"
app_email = "you@example.com"
app_license = "MIT"

# Refuse to install unless erpnext is already on the site.
required_apps = ["erpnext"]

# Custom Fields added to erpnext's own doctypes, shipped as data (not by
# editing erpnext's source) so they survive every erpnext upgrade.
fixtures = [
	{
		"dt": "Custom Field",
		"filters": [["dt", "in", ["Pick List Item", "Stock Entry Detail"]]],
	},
	{
		"dt": "Print Format",
		"filters": [["name", "in", ["Bin Location Label"]]],
	},
]

# Roles shipped with this app. Frappe creates them on `bench migrate`.
roles = [
	{
		"role_name": "Warehouse Technician",
		"role_desk_access": 0,  # Technicians use the scanning UI, not the desk
	}
]

# This is the entire coupling surface to erpnext. No monkeypatching, no
# subclassing erpnext controllers — just subscribing to lifecycle events
# Frappe fires on documents, including ones owned by another app.
# Barcode rendering for print formats. Registers get_barcode_svg as a
# Jinja global so print format templates can call {{ get_barcode_svg(value) }}
# to generate inline Code128 (or other) barcode SVGs.
jinja = {
	"methods": [
		"warehouse_binning.utils.get_barcode_svg",
	]
}

doc_events = {
	"Purchase Receipt": {
		"on_submit": "warehouse_binning.events.purchase_receipt.create_putaway_tasks"
	},
	"Stock Entry": {
		"before_submit": "warehouse_binning.events.stock_entry.validate_bin_pick",
		"on_submit": "warehouse_binning.events.stock_entry.update_bin_ledger",
		"on_cancel": "warehouse_binning.events.stock_entry.reverse_bin_ledger",
	},
	"Pick List": {
		"validate": "warehouse_binning.events.pick_list.suggest_bins"
	},
	"Work Order": {
		"on_submit": "warehouse_binning.events.work_order.create_pick_tasks"
	},
	"Material Request": {
		"on_submit": "warehouse_binning.events.material_request.create_pick_tasks"
	},
}
