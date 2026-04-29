# Copyright (c) 2025, hello@frappe.io and Contributors
# See license.txt

import hashlib
import hmac
import json

import frappe
from frappe.tests import IntegrationTestCase
from frappe.tests.test_api import make_request
from frappe.utils import get_test_client

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class IntegrationTestDigioSettings(IntegrationTestCase):
	"""
	Integration tests for DigioSettings.
	Use this class for testing interactions between multiple components.
	"""

	TEST_CLIENT = get_test_client()

	def setUp(self):
		frappe.reload_doc("ekyc_india", "doctype", "digio_settings")
		super().setUp()

	def test_handle_digio_webhook_accepts_valid_checksum(self):
		settings = frappe.get_single("Digio Settings")
		settings.enable_sandbox = 1
		settings.sandbox_webhook_secret = "sandbox-secret"
		settings.save(ignore_permissions=True)

		request_log = frappe.get_doc(
			{
				"doctype": "Digio Request Log",
				"digio_id": "KID-0001",
				"response_json": json.dumps({"id": "KID-0001"}),
			}
		).insert(ignore_permissions=True)
		frappe.db.commit()

		payload = {
			"id": "WHN-0001",
			"event": "KYC_REQUEST_APPROVED",
			"payload": {
				"KYC_REQUEST": {
					"id": "KID-0001",
					"reference_id": "CUS-0001",
					"transaction_id": "TXN-0001",
				}
			},
		}
		raw_payload = json.dumps(payload)
		checksum = hmac.new(b"sandbox-secret", raw_payload.encode("utf-8"), hashlib.sha256).hexdigest()

		response = make_request(
			target=self.TEST_CLIENT.post,
			args=(
				"/api/method/ekyc_india.ekyc_india.doctype.digio_settings.digio_settings.handle_digio_webhook",
			),
			kwargs={
				"data": raw_payload,
				"content_type": "application/json",
				"headers": {"X-Digio-Checksum": checksum},
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["message"]["status"], "accepted")

		frappe.db.rollback()
		updated_request_log = frappe.get_doc("Digio Request Log", request_log.name)
		self.assertIn("_last_webhook_event", updated_request_log.response_json)
		self.assertTrue(
			frappe.db.exists(
				"Webhook Request Log",
				{"reference_doctype": "Digio Request Log", "reference_document": request_log.name},
			)
		)

	def test_handle_digio_webhook_rejects_invalid_checksum(self):
		settings = frappe.get_single("Digio Settings")
		settings.enable_sandbox = 1
		settings.sandbox_webhook_secret = "sandbox-secret"
		settings.save(ignore_permissions=True)
		frappe.db.commit()

		payload = {"id": "WHN-0002", "event": "DOC.SIGNED", "payload": {"document": {"id": "DID-1"}}}
		response = make_request(
			target=self.TEST_CLIENT.post,
			args=(
				"/api/method/ekyc_india.ekyc_india.doctype.digio_settings.digio_settings.handle_digio_webhook",
			),
			kwargs={
				"data": json.dumps(payload),
				"content_type": "application/json",
				"headers": {"X-Digio-Checksum": "invalid"},
			},
		)

		self.assertEqual(response.status_code, 403)
		self.assertEqual(response.json["message"]["status"], "rejected")
