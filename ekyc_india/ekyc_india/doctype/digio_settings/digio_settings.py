# Copyright (c) 2025, hello@frappe.io and contributors
# For license information, please see license.txt

import base64
import json

import frappe
from frappe.integrations.utils import make_request
from frappe.model.document import Document
from frappe.utils.password import get_decrypted_password


class DigioSettings(Document):
	pass


def make_esignature_request(doc):
	general_settings = get_general_settings()
	signers = []
	signer_emails = get_signers(doc)

	for signer in signer_emails:
		signers.append(
			{
				"identifier": signer,
				"name": get_customer_name(signer),
				"sign_type": "aadhaar",
				"reason": "Please sign the document",
			}
		)

	request = frappe._dict()
	request.update(
		{
			"signers": signers,
			"expire_in_days": general_settings.get("expire_in_days"),
			"notify_signers": bool(general_settings.get("notify_customer")),
			"send_sign_link": bool(general_settings.get("send_sign_link")),
			"generate_access_token": bool(general_settings.get("generate_access_token")),
			"file_name": doc.name,
			"file_data": get_file_data_in_base64(doc.doctype, doc.name),
		}
	)

	send_esignature_request(request)


def send_esignature_request(body):
	api_client_id, api_client_secret, base_url = get_api_credentials_and_url()
	url = f"{base_url}/v2/client/document/uploadpdf"

	response = make_request(
		method="POST", url=url, headers=get_headers(api_client_id, api_client_secret), json=body
	)

	make_digio_request_log(response)


def make_digio_request_log(response):
	doc = frappe.new_doc("Digio Request Log")
	doc.digio_id = response.get("id")
	doc.response_json = json.dumps(response, indent=1)
	doc.save(ignore_permissions=True)


def get_api_credentials_and_url():
	digio_settings = frappe.get_doc("Digio Settings", "Digio Settings")

	if digio_settings.enable_production:
		api_client_id = get_decrypted_password(
			"Digio Settings", "Digio Settings", fieldname="api_client_id", raise_exception=False
		)
		api_client_secret = get_decrypted_password(
			"Digio Settings", "Digio Settings", fieldname="api_client_secret", raise_exception=False
		)
		url = frappe.get_single_value("Digio Settings", "production_url")
	else:
		if not digio_settings.enable_sandbox:
			frappe.throw("Please enable Sandbox or Production mode in Digio Settings")

		api_client_id = get_decrypted_password(
			"Digio Settings", "Digio Settings", fieldname="sandbox_api_client_id", raise_exception=False
		)
		api_client_secret = get_decrypted_password(
			"Digio Settings", "Digio Settings", fieldname="sandbox_api_secret", raise_exception=False
		)
		url = frappe.get_single_value("Digio Settings", "sandbox_url")

	return api_client_id, api_client_secret, url


def get_file_data_in_base64(doctype, docname):
	file_data = base64.b64encode(
		frappe.get_print(doctype, docname, as_pdf=True, pdf_generator="wkhtmltopdf")
	).decode()

	return file_data


def get_signers(doc):
	from frappe.email.doctype.notification.notification import _parse_receiver_by_document_field

	signers = []
	receiver_fields = frappe.db.get_all(
		"e-Signature Document",
		filters={"document_type": doc.doctype},
		fields=["request_recipient_by_document_field"],
	)

	for receiver in receiver_fields:
		data_field, child_field = _parse_receiver_by_document_field(
			receiver.request_recipient_by_document_field
		)

		if child_field:
			for d in doc.get(child_field):
				email_id = d.get(data_field)
				signers.append(email_id)
		# field from current doc
		else:
			email_ids_value = doc.get(data_field)
			email_ids = email_ids_value.replace(",", "\n")
			signers = signers + email_ids.split("\n")

	return signers


def make_ekyc_request(doc):
	signers = get_signers(doc)
	general_settings = get_general_settings()

	# will send a separate eKYC request for each signer
	for signer in signers:
		request = frappe._dict()
		request.update(
			{
				"customer_identifier": signer,
				"notify_customer": True,
				"customer_name": get_customer_name(signer),
				"template_name": "DIGILOCKER_AADHAAR_PAN",
				"expire_in_days": general_settings.get("expire_in_days"),
				"generate_access_token": general_settings.get("generate_access_token"),
				"reference_id": doc.name,
				"transaction_id": frappe.generate_hash(length=12),
				"generate_deeplink_info": False,
			}
		)

		send_ekyc_request(request)


def get_customer_name(email_id):
	customer_name = frappe.db.get_value("Customer", {"email_id": email_id}, "customer_name")

	if not customer_name:
		# TODO: fetch name from linked Lead or Contact
		customer_name = ""

	return customer_name


def send_ekyc_request(body):
	api_client_id, api_client_secret, base_url = get_api_credentials_and_url()
	url = f"{base_url}/client/kyc/v2/request/with_template"

	response = make_request(
		method="POST", url=url, headers=get_headers(api_client_id, api_client_secret), json=body
	)

	make_digio_request_log(response)


def get_general_settings():
	doc = frappe.get_doc("Digio Settings", "Digio Settings")
	return {
		"expire_in_days": doc.request_expiry_in_days,
		"notify_customer": doc.notify_customers,
		"generate_access_token": doc.generate_access_token,
		"send_sign_link": doc.send_sign_link,
	}


def get_headers(api_client_id, api_client_secret):
	headers = {
		"Content-Type": "application/json",
		"Accept": "application/json",
		"Authorization": "Basic"
		+ base64.b64encode((api_client_id + ":" + api_client_secret).encode("utf-8")).decode(),
	}

	return headers


@frappe.whitelist()
def update_digio_settings(production_url, api_client_id, api_secret):
	doc = frappe.get_single("Digio Settings")
	doc.enable_production = 1
	doc.production_url = production_url
	doc.api_client_id = api_client_id
	doc.api_secret = api_secret
	doc.save()
