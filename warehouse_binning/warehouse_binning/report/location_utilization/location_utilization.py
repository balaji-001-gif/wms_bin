import frappe
from frappe import _


def execute(filters=None):
	columns = [
		{
			"fieldname": "bin_location",
			"label": _("Bin Location"),
			"fieldtype": "Link",
			"options": "Bin Location",
			"width": 200,
		},
		{
			"fieldname": "warehouse",
			"label": _("Warehouse"),
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 120,
		},
		{
			"fieldname": "zone",
			"label": _("Zone"),
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"fieldname": "rack",
			"label": _("Rack"),
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"fieldname": "capacity",
			"label": _("Capacity"),
			"fieldtype": "Float",
			"width": 100,
		},
		{
			"fieldname": "current_usage",
			"label": _("Current Usage"),
			"fieldtype": "Float",
			"width": 100,
		},
		{
			"fieldname": "available",
			"label": _("Available"),
			"fieldtype": "Float",
			"width": 100,
		},
		{
			"fieldname": "utilization_pct",
			"label": _("Utilization %"),
			"fieldtype": "Percent",
			"width": 100,
		},
		{
			"fieldname": "status",
			"label": _("Status"),
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"fieldname": "is_active",
			"label": _("Active"),
			"fieldtype": "Check",
			"width": 60,
		},
	]

	conditions = ""
	if filters:
		conds = []
		if filters.get("warehouse"):
			conds.append("bl.warehouse = %(warehouse)s")
		if filters.get("zone"):
			conds.append("bl.zone = %(zone)s")
		if filters.get("status") == "Full":
			conds.append("COALESCE(usage_data.used, 0) >= COALESCE(bl.capacity, 0)")
		elif filters.get("status") == "Available":
			conds.append("COALESCE(bl.capacity, 0) > COALESCE(usage_data.used, 0)")
		elif filters.get("status") == "Empty":
			conds.append("COALESCE(usage_data.used, 0) = 0")
		if conds:
			conditions = "AND " + " AND ".join(conds)

	data = frappe.db.sql(
		"""
		SELECT
			bl.name AS bin_location,
			bl.warehouse,
			COALESCE(bl.zone, '') AS zone,
			COALESCE(bl.rack, '') AS rack,
			COALESCE(bl.capacity, 0) AS capacity,
			COALESCE(usage_data.used, 0) AS current_usage,
			GREATEST(COALESCE(bl.capacity, 0) - COALESCE(usage_data.used, 0), 0) AS available,
			CASE
				WHEN COALESCE(bl.capacity, 0) > 0
				THEN ROUND((COALESCE(usage_data.used, 0) / bl.capacity) * 100, 1)
				ELSE 0
			END AS utilization_pct,
			CASE
				WHEN bl.capacity IS NULL OR bl.capacity = 0 THEN 'Not Set'
				WHEN COALESCE(usage_data.used, 0) = 0 THEN 'Empty'
				WHEN COALESCE(usage_data.used, 0) >= bl.capacity THEN 'Full'
				ELSE 'Available'
			END AS status,
			COALESCE(bl.is_active, 1) AS is_active
		FROM `tabBin Location` bl
		LEFT JOIN (
			SELECT bin_location, SUM(qty) AS used
			FROM `tabItem Batch Bin Stock`
			GROUP BY bin_location
		) usage_data ON usage_data.bin_location = bl.name
		WHERE 1=1 {conditions}
		ORDER BY bl.warehouse, bl.name
		""".format(
			conditions=conditions
		),
		filters or {},
		as_dict=True,
	)

	return columns, data
