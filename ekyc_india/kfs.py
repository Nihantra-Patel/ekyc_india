# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, add_to_date, cint, flt, getdate, rounded

from ekyc_india.lending_utils import if_lending_app_installed


@if_lending_app_installed
def loan_application_before_save(doc, method=None):
	if doc.get("kfs_generated"):
		build_kfs(doc)
		return

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


def set_kfs_validity(doc):
	tenor_days = flt(doc.repayment_periods) * 30
	working_days = 3 if tenor_days >= 7 else 1
	doc.kfs_valid_till = add_working_days(getdate(doc.posting_date), working_days)


def set_kfs_charges(doc):
	if doc.get("kfs_charges"):
		return

	product_charges = frappe.get_all(
		"Loan Charges",
		filters={"parent": doc.loan_product},
		fields=["charge_type", "amount"],
	)
	for charge in product_charges:
		doc.append(
			"kfs_charges",
			{
				"charge_name": charge.charge_type,
				"payable_to": "Regulated Entity",
				"amount": flt(charge.amount),
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

	balance = flt(doc.loan_amount)
	epi = flt(doc.repayment_amount)
	monthly_rate = flt(doc.rate_of_interest) / (12 * 100)
	payment_date = getdate(doc.posting_date)

	for instalment_no in range(1, cint(doc.repayment_periods) + 1):
		interest_amount = rounded(balance * monthly_rate)
		principal_amount = rounded(epi - interest_amount)

		if instalment_no == cint(doc.repayment_periods) or principal_amount > balance:
			principal_amount = balance
			epi_amount = rounded(principal_amount + interest_amount)
		else:
			epi_amount = epi

		opening_balance = balance
		balance = rounded(balance - principal_amount)

		payment_date = add_to_date(payment_date, months=1)

		doc.append(
			"kfs_schedule",
			{
				"instalment_no": instalment_no,
				"payment_date": payment_date,
				"outstanding_principal": opening_balance,
				"principal_amount": principal_amount,
				"interest_amount": interest_amount,
				"instalment_amount": epi_amount,
			},
		)

		if balance <= 0:
			break


def calculate_apr(doc):
	apr_charges = get_total_kfs_charges(doc, only_apr=True)
	doc.net_disbursed_amount = flt(doc.loan_amount) - apr_charges

	if not doc.net_disbursed_amount or not doc.get("kfs_schedule"):
		doc.annual_percentage_rate = doc.rate_of_interest
		return

	cash_flows = [(getdate(doc.posting_date), -flt(doc.net_disbursed_amount))]
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
