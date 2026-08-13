# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, rounded

from ekyc_india.lending_utils import if_lending_app_installed


@if_lending_app_installed
def loan_application_before_save(doc, method=None):
	if (
		doc.get("is_term_loan")
		and doc.get("loan_amount")
		and doc.get("rate_of_interest")
		and doc.get("repayment_periods")
	):
		build_kfs(doc)


def build_kfs(doc):
	if not doc.get("is_term_loan"):
		frappe.throw(_("Key Facts Statement can be generated only for term loans."))

	if not (doc.get("loan_amount") and doc.get("rate_of_interest") and doc.get("repayment_periods")):
		frappe.throw(
			_("Loan Amount, Rate of Interest and Repayment Periods are required to generate the KFS.")
		)

	doc.get_repayment_details()

	if not doc.get("unique_proposal_number"):
		doc.unique_proposal_number = doc.name or frappe.generate_hash(length=10).upper()

	if not doc.get("loan_type"):
		doc.loan_type = frappe.db.get_value("Loan Product", doc.loan_product, "product_name")

	set_kfs_validity(doc)
	set_kfs_charges(doc)
	build_kfs_schedule(doc)
	calculate_apr(doc)
	doc.kfs_generated = 1
	doc.borrower_acknowledged = 0


def set_kfs_validity(doc):
	doc.kfs_valid_till = add_working_days(getdate(), 3)


def set_kfs_charges(doc):
	if doc.get("kfs_charges"):
		return

	product_charges = frappe.get_all(
		"Loan Charges",
		filters={"parent": doc.loan_product},
		fields=["charge_type", "charge_based_on", "amount", "percentage"],
	)
	for charge in product_charges:
		if charge.charge_based_on == "Percentage":
			amount = flt(doc.loan_amount) * flt(charge.percentage) / 100
		else:
			amount = flt(charge.amount)

		doc.append(
			"kfs_charges",
			{
				"charge": charge.charge_type,
				"payable_to": "Regulated Entity",
				"amount": amount,
				"included_in_apr": 1,
			},
		)


def get_total_kfs_charges(doc, only_apr=False):
	total = 0
	for charge in doc.get("kfs_charges") or []:
		if only_apr and not charge.included_in_apr:
			continue
		total += flt(charge.amount)
	return total


def build_kfs_schedule(doc):
	doc.set("kfs_schedule", [])

	for instalment_no, row in enumerate(get_proposed_repayment_schedule(doc), start=1):
		doc.append(
			"kfs_schedule",
			{
				"instalment_no": instalment_no,
				"payment_date": row.payment_date,
				"outstanding_principal": flt(row.balance_loan_amount) + flt(row.principal_amount),
				"principal_amount": row.principal_amount,
				"interest_amount": row.interest_amount,
				"instalment_amount": row.total_payment,
			},
		)


def get_proposed_repayment_schedule(doc):
	repayment_schedule = frappe.new_doc("Loan Repayment Schedule")
	repayment_schedule.loan_product = doc.loan_product
	repayment_schedule.repayment_frequency = "Monthly"
	repayment_schedule.repayment_method = "Repay Over Number of Periods"
	repayment_schedule.repayment_periods = doc.repayment_periods
	repayment_schedule.rate_of_interest = doc.rate_of_interest
	repayment_schedule.posting_date = getdate()
	repayment_schedule.repayment_start_date = getdate()
	repayment_schedule.loan_amount = doc.loan_amount
	repayment_schedule.current_principal_amount = doc.loan_amount
	repayment_schedule.moratorium_tenure = 0
	repayment_schedule.moratorium_type = ""
	repayment_schedule.repayment_schedule_type = frappe.db.get_value(
		"Loan Product", doc.loan_product, "repayment_schedule_type"
	)
	repayment_schedule.validate()

	return repayment_schedule.get("repayment_schedule")


def calculate_apr(doc):
	apr_charges = get_total_kfs_charges(doc, only_apr=True)
	doc.net_disbursed_amount = flt(doc.loan_amount) - apr_charges

	if not doc.net_disbursed_amount or not doc.get("kfs_schedule"):
		doc.annual_percentage_rate = doc.rate_of_interest
		return

	cash_flows = [(getdate(), -flt(doc.net_disbursed_amount))]
	for row in doc.kfs_schedule:
		cash_flows.append((getdate(row.payment_date), flt(row.instalment_amount)))

	apr = xirr(cash_flows)
	doc.annual_percentage_rate = rounded(apr * 100, 2) if apr is not None else doc.rate_of_interest


def add_working_days(start_date, working_days):
	current = getdate(start_date)
	added = 0
	while added < working_days:
		current = add_days(current, 1)
		if current.weekday() < 5:
			added += 1
	return current


def xirr(cash_flows, guess=0.1):
	if not cash_flows:
		return None

	base_date = getdate(cash_flows[0][0])

	def npv(rate):
		total = 0.0
		for date, amount in cash_flows:
			years = (getdate(date) - base_date).days / 365.0
			total += amount / ((1 + rate) ** years)
		return total

	rate = guess
	for _i in range(100):
		value = npv(rate)
		delta = 1e-6
		derivative = (npv(rate + delta) - value) / delta
		if not derivative:
			break
		new_rate = rate - value / derivative
		if abs(new_rate - rate) < 1e-8:
			return new_rate
		rate = new_rate

	low, high = -0.9999, 10.0
	f_low = npv(low)
	for _i in range(200):
		mid = (low + high) / 2
		f_mid = npv(mid)
		if abs(f_mid) < 1e-6:
			return mid
		if (f_low < 0) != (f_mid < 0):
			high = mid
		else:
			low, f_low = mid, f_mid
	return None


@frappe.whitelist()
@if_lending_app_installed
def generate_kfs(loan_application: str):
	doc = frappe.get_doc("Loan Application", loan_application)
	doc.check_permission("write")
	build_kfs(doc)
	doc.save()
	return doc.name


@frappe.whitelist()
@if_lending_app_installed
def acknowledge_kfs(loan_application: str):
	doc = frappe.get_doc("Loan Application", loan_application)
	doc.check_permission("write")

	if not doc.get("kfs_generated"):
		frappe.throw(_("Generate the Key Facts Statement (KFS) before recording acknowledgement."))

	doc.db_set("borrower_acknowledged", 1)
	return doc.name
