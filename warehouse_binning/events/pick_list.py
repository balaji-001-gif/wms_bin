import frappe


def suggest_bins(doc, method):
	"""On validate: for any Pick List Item without a bin already set, suggest
	the bin holding the earliest-expiring batch of that item in the warehouse
	(FEFO — First-Expiry-First-Out).

	Batches without an expiry date are sorted last so they are only
	suggested when no expiring batch exists. Among rows with the same
	expiry date, the bin with the most stock is preferred.

	Requires the Item to have shelf-life management enabled (Has Batch No
	and Has Expiry Date) for expiry dates to be populated on Batch records.
	"""
	for row in doc.locations:
		if row.get("bin_location"):
			continue

		bins = frappe.db.sql(
			"""
			SELECT ibbs.bin_location, ibbs.batch_no, ibbs.qty, b.expiry_date
			FROM `tabItem Batch Bin Stock` ibbs
			LEFT JOIN `tabBatch` b ON b.name = ibbs.batch_no
			WHERE ibbs.item_code = %s
			  AND ibbs.warehouse = %s
			  AND ibbs.qty > 0
			ORDER BY
			  COALESCE(b.expiry_date, '2099-12-31') ASC,
			  ibbs.qty DESC
			LIMIT 1
			""",
			(row.item_code, row.warehouse),
			as_dict=True,
		)

		if not bins:
			continue
		row.bin_location = bins[0].bin_location
		if not row.batch_no:
			row.batch_no = bins[0].batch_no
