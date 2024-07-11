# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate

import erpnext
from erpnext.accounts.general_ledger import make_gl_entries
from erpnext.controllers.accounts_controller import AccountsController

from lending.loan_management.doctype.loan_repayment.loan_repayment import get_net_paid_amount


class LoanRefund(AccountsController):
	"""
	Add refund if total repayment is more than that is owed.
	"""

	def validate(self):
		self.set_missing_values()
		# self.validate_refund_amount()

	def set_missing_values(self):
		if not self.cost_center:
			self.cost_center = erpnext.get_default_cost_center(self.company)

	def validate_refund_amount(self):
		net_paid_amount = get_net_paid_amount(self.loan)

		if net_paid_amount - self.refund_amount < 0:
			frappe.throw(_("Refund amount cannot be greater than net paid amount"))

	def on_submit(self):
		self.update_outstanding_amount()
		self.make_gl_entries()

	def on_cancel(self):
		self.update_outstanding_amount(cancel=1)
		self.ignore_linked_doctypes = ["GL Entry", "Payment Ledger Entry"]
		self.make_gl_entries(cancel=1)

	def update_outstanding_amount(self, cancel=0):
		refund_amount = frappe.db.get_value("Loan", self.loan, "refund_amount")

		if cancel:
			refund_amount -= self.refund_amount
		else:
			refund_amount += self.refund_amount

		frappe.db.set_value("Loan", self.loan, "refund_amount", refund_amount)

	def make_gl_entries(self, cancel=0):
		gl_entries = []
		loan_details = frappe.get_doc("Loan", self.loan)

		gl_entries.append(
			self.get_gl_dict(
				{
					"account": loan_details.loan_account,
					"against": loan_details.loan_account,
					"credit": self.refund_amount,
					"credit_in_account_currency": self.refund_amount,
					"against_voucher_type": "Loan",
					"against_voucher": self.loan,
					"remarks": _("Against Loan:") + self.loan,
					"cost_center": self.cost_center,
					"posting_date": getdate(self.posting_date),
					"party_type": loan_details.applicant_type,
					"party": loan_details.applicant,
				}
			)
		)

		gl_entries.append(
			self.get_gl_dict(
				{
					"account": self.refund_account,
					"against": self.refund_account,
					"debit": self.refund_amount,
					"debit_in_account_currency": self.refund_amount,
					"against_voucher_type": "Loan",
					"against_voucher": self.loan,
					"remarks": _("Against Loan:") + self.loan,
					"cost_center": self.cost_center,
					"posting_date": getdate(self.posting_date),
				}
			)
		)

		make_gl_entries(gl_entries, cancel=cancel, merge_entries=False)
