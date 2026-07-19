# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from ekyc_india.lending_utils import if_lending_app_installed

KFS_CUSTOM_FIELDS = {
	"Loan Application": [
		{
			"fieldname": "kfs_tab",
			"fieldtype": "Tab Break",
			"label": "Key Facts Statement",
			"insert_after": "documents",
		},
		{
			"fieldname": "kfs_generated",
			"fieldtype": "Check",
			"label": "KFS Generated",
			"default": "0",
			"read_only": 1,
			"no_copy": 1,
			"insert_after": "kfs_tab",
		},
		{
			"fieldname": "kfs_section",
			"fieldtype": "Section Break",
			"label": "Key Facts (Annex A - Part 1)",
			"insert_after": "kfs_generated",
		},
		{
			"fieldname": "generate_kfs_button",
			"fieldtype": "Button",
			"label": "Regenerate KFS",
			"description": "Refresh the KFS on demand, e.g. after changing fees or charges.",
			"depends_on": "eval: doc.is_term_loan == 1 && doc.kfs_generated == 1",
			"insert_after": "kfs_section",
		},
		{
			"fieldname": "unique_proposal_number",
			"fieldtype": "Data",
			"label": "Loan Proposal / Account No.",
			"read_only": 1,
			"no_copy": 1,
			"insert_after": "generate_kfs_button",
		},
		{
			"fieldname": "loan_type",
			"fieldtype": "Data",
			"label": "Type of Loan",
			"read_only": 1,
			"insert_after": "unique_proposal_number",
		},
		{
			"fieldname": "column_break_kfs_a",
			"fieldtype": "Column Break",
			"insert_after": "loan_type",
		},
		{
			"fieldname": "kfs_valid_till",
			"fieldtype": "Date",
			"label": "KFS Valid Till",
			"read_only": 1,
			"no_copy": 1,
			"description": "Borrower has at least 3 working days (1 working day for tenor below 7 days) to accept the KFS.",
			"insert_after": "column_break_kfs_a",
		},
		{
			"fieldname": "net_disbursed_amount",
			"fieldtype": "Currency",
			"label": "Net Disbursed Amount",
			"read_only": 1,
			"insert_after": "kfs_valid_till",
		},
		{
			"fieldname": "annual_percentage_rate",
			"fieldtype": "Percent",
			"label": "Annual Percentage Rate (APR)",
			"read_only": 1,
			"description": "All-inclusive annual cost of credit including interest and all charges.",
			"insert_after": "net_disbursed_amount",
		},
		{
			"fieldname": "kfs_charges_section",
			"fieldtype": "Section Break",
			"label": "Fees / Charges",
			"insert_after": "annual_percentage_rate",
		},
		{
			"fieldname": "kfs_charges",
			"fieldtype": "Table",
			"label": "Fees / Charges",
			"options": "Loan Application Charge",
			"insert_after": "kfs_charges_section",
		},
		{
			"fieldname": "kfs_schedule_section",
			"fieldtype": "Section Break",
			"label": "Repayment Schedule (Annex C)",
			"collapsible": 1,
			"insert_after": "kfs_charges",
		},
		{
			"fieldname": "kfs_schedule",
			"fieldtype": "Table",
			"label": "Repayment Schedule",
			"options": "Loan Application KFS Schedule",
			"read_only": 1,
			"no_copy": 1,
			"insert_after": "kfs_schedule_section",
		},
		{
			"fieldname": "qualitative_info_section",
			"fieldtype": "Section Break",
			"label": "Other Qualitative Information (Annex A - Part 2)",
			"insert_after": "kfs_schedule",
		},
		{
			"fieldname": "recovery_agent_clause",
			"fieldtype": "Small Text",
			"label": "Recovery Agents Clause",
			"insert_after": "qualitative_info_section",
		},
		{
			"fieldname": "grievance_redressal_clause",
			"fieldtype": "Small Text",
			"label": "Grievance Redressal Clause",
			"insert_after": "recovery_agent_clause",
		},
		{
			"fieldname": "column_break_kfs_c",
			"fieldtype": "Column Break",
			"insert_after": "grievance_redressal_clause",
		},
		{
			"fieldname": "nodal_officer_phone",
			"fieldtype": "Data",
			"label": "Nodal Grievance Officer Phone",
			"insert_after": "column_break_kfs_c",
		},
		{
			"fieldname": "nodal_officer_email",
			"fieldtype": "Data",
			"label": "Nodal Grievance Officer Email",
			"options": "Email",
			"insert_after": "nodal_officer_phone",
		},
		{
			"fieldname": "kfs_acknowledgement_section",
			"fieldtype": "Section Break",
			"label": "Borrower Acknowledgement",
			"insert_after": "nodal_officer_email",
		},
		{
			"fieldname": "borrower_acknowledged",
			"fieldtype": "Check",
			"label": "Borrower Acknowledged Understanding",
			"default": "0",
			"description": "Borrower has been explained and has acknowledged understanding of the Key Facts Statement.",
			"insert_after": "kfs_acknowledgement_section",
		},
	]
}


KFS_CUSTOM_FIELD_NAMES = [field["fieldname"] for fields in KFS_CUSTOM_FIELDS.values() for field in fields]

KFS_OBSOLETE_FIELD_NAMES = [
	"interest_rate_type",
	"floating_rate_section",
	"interest_rate_benchmark",
	"spread_over_benchmark",
	"column_break_kfs_b",
	"reset_periodicity",
]


@if_lending_app_installed
def remove_obsolete_kfs_fields():
	for fieldname in KFS_OBSOLETE_FIELD_NAMES:
		name = frappe.db.get_value("Custom Field", {"dt": "Loan Application", "fieldname": fieldname})
		if name:
			frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)


@if_lending_app_installed
def create_kfs_custom_fields():
	create_custom_fields(KFS_CUSTOM_FIELDS, ignore_validate=True)


@if_lending_app_installed
def remove_kfs_custom_fields():
	for fieldname in KFS_CUSTOM_FIELD_NAMES:
		name = frappe.db.get_value("Custom Field", {"dt": "Loan Application", "fieldname": fieldname})
		if name:
			frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)
