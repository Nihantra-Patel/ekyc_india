# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class LoanApplicationCharge(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount: DF.Currency
		charge_name: DF.Data
		included_in_apr: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		payable_to: DF.Literal["Regulated Entity", "Third Party"]
	# end: auto-generated types

	pass
