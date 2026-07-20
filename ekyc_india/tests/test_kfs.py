# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# See license.txt

import datetime
import unittest

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from ekyc_india.kfs import acknowledge_kfs, add_working_days, build_kfs, xirr

LENDING_INSTALLED = "lending" in frappe.get_installed_apps()


class UnitTestKFSCalculations(UnitTestCase):
	def test_add_working_days_skips_weekend(self):
		friday = datetime.date(2026, 6, 19)
		self.assertEqual(add_working_days(friday, 3), datetime.date(2026, 6, 24))

	def test_add_one_working_day(self):
		friday = datetime.date(2026, 6, 19)
		self.assertEqual(add_working_days(friday, 1), datetime.date(2026, 6, 22))

	def test_xirr_matches_nominal_rate_without_charges(self):
		loan, rate, n = 100000.0, 12.0, 12
		monthly = rate / 1200
		epi = loan * monthly * (1 + monthly) ** n / ((1 + monthly) ** n - 1)

		start = datetime.date(2026, 1, 1)
		cash_flows = [(start, -loan)]
		due = start
		for _i in range(n):
			month = due.month % 12 + 1
			year = due.year + (1 if due.month == 12 else 0)
			due = datetime.date(year, month, 1)
			cash_flows.append((due, epi))

		apr = xirr(cash_flows) * 100
		self.assertGreater(apr, 12.0)
		self.assertLess(apr, 13.0)

	def test_xirr_returns_none_for_empty(self):
		self.assertIsNone(xirr([]))


@unittest.skipUnless(LENDING_INSTALLED, "Lending app is not installed")
class IntegrationTestKFSOnLoanApplication(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		from erpnext.setup.doctype.employee.test_employee import make_employee
		from lending.tests.test_utils import (
			create_loan_accounts,
			create_loan_product,
			set_loan_settings_in_company,
		)

		set_loan_settings_in_company()
		create_loan_accounts()
		create_loan_product(
			"KFS Home Loan",
			"KFS Home Loan",
			500000,
			9.2,
			0,
			1,
			0,
			repayment_schedule_type="Monthly as per repayment start date",
		)
		cls.applicant = make_employee("kfs_kate@loan.com", "_Test Company")

		if not frappe.db.exists("Item", "Processing Fee"):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": "Processing Fee",
					"item_name": "Processing Fee",
					"item_group": "All Item Groups",
					"is_stock_item": 0,
				}
			).insert(ignore_permissions=True)

	def make_application(self):
		loan_application = frappe.new_doc("Loan Application")
		loan_application.update(
			{
				"applicant_type": "Employee",
				"applicant": self.applicant,
				"loan_product": "KFS Home Loan",
				"rate_of_interest": 9.2,
				"loan_amount": 250000,
				"repayment_method": "Repay Over Number of Periods",
				"repayment_periods": 18,
				"company": "_Test Company",
				"applicant_email_address": "lending@example.com",
				"applicant_phone_number": "+91-9102837465",
			}
		)
		loan_application.insert()
		return loan_application

	def test_kfs_generation(self):
		doc = self.make_application()
		build_kfs(doc)

		self.assertTrue(doc.kfs_generated)
		self.assertTrue(doc.unique_proposal_number)
		self.assertTrue(doc.kfs_valid_till)
		self.assertEqual(len(doc.kfs_schedule), doc.repayment_periods)

	def test_kfs_schedule_closes_principal(self):
		doc = self.make_application()
		build_kfs(doc)

		self.assertEqual(doc.kfs_schedule[0].outstanding_principal, doc.loan_amount)

		total_principal = sum(row.principal_amount for row in doc.kfs_schedule)
		self.assertAlmostEqual(total_principal, doc.loan_amount, delta=1)

		last_row = doc.kfs_schedule[-1]
		closing_balance = last_row.outstanding_principal - last_row.principal_amount
		self.assertAlmostEqual(closing_balance, 0, delta=1)

	def test_kfs_apr_includes_charges(self):
		doc = self.make_application()
		doc.append(
			"kfs_charges",
			{
				"charge": "Processing Fee",
				"payable_to": "Regulated Entity",
				"amount": 5000,
				"included_in_apr": 1,
			},
		)
		build_kfs(doc)

		self.assertEqual(doc.net_disbursed_amount, doc.loan_amount - 5000)
		self.assertGreater(doc.annual_percentage_rate, doc.rate_of_interest)

	def test_kfs_requires_term_loan(self):
		doc = self.make_application()
		doc.is_term_loan = 0
		self.assertRaises(frappe.ValidationError, build_kfs, doc)

	def test_kfs_auto_generated_on_save(self):
		doc = self.make_application()
		self.assertTrue(doc.kfs_generated)
		self.assertTrue(doc.annual_percentage_rate)
		self.assertEqual(len(doc.kfs_schedule), doc.repayment_periods)

	def test_esign_blocked_until_kfs_acknowledged(self):
		from ekyc_india.ekyc_india.doctype.digio_settings.digio_settings import (
			check_kfs_before_esign,
		)

		doc = self.make_application()
		frappe.db.set_single_value("Digio Settings", "enforce_kfs_before_esign", 1)

		self.assertRaises(frappe.ValidationError, check_kfs_before_esign, doc)

		doc.borrower_acknowledged = 1
		check_kfs_before_esign(doc)

		doc.borrower_acknowledged = 0
		frappe.db.set_single_value("Digio Settings", "enforce_kfs_before_esign", 0)
		check_kfs_before_esign(doc)
		frappe.db.set_single_value("Digio Settings", "enforce_kfs_before_esign", 1)

	def test_borrower_acknowledged_is_read_only(self):
		field = frappe.get_meta("Loan Application").get_field("borrower_acknowledged")
		self.assertEqual(field.read_only, 1)

	def test_acknowledge_kfs_requires_kfs_generated(self):
		doc = self.make_application()
		doc.db_set("kfs_generated", 0)
		self.assertRaises(frappe.ValidationError, acknowledge_kfs, doc.name)

	def test_acknowledge_kfs_sets_flag(self):
		doc = self.make_application()
		self.assertFalse(doc.borrower_acknowledged)

		acknowledge_kfs(doc.name)

		self.assertEqual(frappe.db.get_value("Loan Application", doc.name, "borrower_acknowledged"), 1)
