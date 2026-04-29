# Copyright (c) 2025, hello@frappe.io and contributors
# For license information, please see license.txt

import base64
import hashlib
import hmac
import json

import frappe
from frappe.integrations.utils import make_request
from frappe.model.document import Document
from frappe.utils import now
from frappe.utils.password import get_decrypted_password

DIGIO_CHECKSUM_HEADER = "X-Digio-Checksum"


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

	make_digio_request_log(response, request_type="digisign", request_payload=body)


def make_digio_request_log(response, request_type=None, request_payload=None):
	log_payload = response.copy() if isinstance(response, dict) else {"response": response}

	if request_type:
		log_payload["_request_type"] = request_type

	if request_payload:
		log_payload["_request_payload"] = request_payload
		log_payload["_reference_id"] = request_payload.get("reference_id") or request_payload.get("file_name")
		log_payload["_transaction_id"] = request_payload.get("transaction_id")

	doc = frappe.new_doc("Digio Request Log")
	doc.digio_id = response.get("id")
	doc.response_json = json.dumps(log_payload, indent=1, sort_keys=True)
	doc.save(ignore_permissions=True)


def get_api_credentials_and_url():
	digio_settings = frappe.get_doc("Digio Settings", "Digio Settings")

	if digio_settings.enable_production:
		api_client_id = get_decrypted_password(
			"Digio Settings", "Digio Settings", fieldname="api_client_id", raise_exception=False
		)
		api_client_secret = get_decrypted_password(
			"Digio Settings", "Digio Settings", fieldname="api_secret", raise_exception=False
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

	make_digio_request_log(response, request_type="digikyc", request_payload=body)


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


def get_digio_webhook_secrets():
	digio_settings = frappe.get_doc("Digio Settings", "Digio Settings")
	secrets = []

	if digio_settings.enable_production:
		production_secret = get_decrypted_password(
			"Digio Settings",
			"Digio Settings",
			fieldname="production_webhook_secret",
			raise_exception=False,
		)
		if production_secret:
			secrets.append(("production", production_secret))

	if digio_settings.enable_sandbox:
		sandbox_secret = get_decrypted_password(
			"Digio Settings",
			"Digio Settings",
			fieldname="sandbox_webhook_secret",
			raise_exception=False,
		)
		if sandbox_secret:
			secrets.append(("sandbox", sandbox_secret))

	return secrets


def validate_digio_webhook_checksum(raw_payload, checksum_header):
	configured_secrets = get_digio_webhook_secrets()
	if not configured_secrets:
		return None

	if not checksum_header:
		frappe.throw("Missing Digio webhook checksum header")

	checksum = checksum_header.strip()
	for environment, secret in configured_secrets:
		expected_checksum = hmac.new(secret.encode("utf-8"), raw_payload, hashlib.sha256).hexdigest()
		if hmac.compare_digest(expected_checksum, checksum):
			return environment

	frappe.throw("Invalid Digio webhook checksum")


def get_digio_request_log_name(digio_id):
	if not digio_id:
		return None

	return frappe.db.get_value("Digio Request Log", {"digio_id": digio_id}, "name")


def update_digio_request_log_from_webhook(payload):
	digio_id = extract_digio_entity_id(payload)
	log_name = get_digio_request_log_name(digio_id)
	if not log_name:
		return None

	doc = frappe.get_doc("Digio Request Log", log_name)
	response_json = load_json_document(doc.response_json)
	response_json["_last_webhook"] = payload
	response_json["_last_webhook_event"] = payload.get("event")
	response_json["_last_webhook_received_at"] = now()
	doc.response_json = json.dumps(response_json, indent=1, sort_keys=True)
	doc.save(ignore_permissions=True)
	return doc


def extract_digio_entity_id(payload):
	digio_document = payload.get("payload", {}).get("document", {})
	if digio_document.get("id"):
		return digio_document.get("id")

	kyc_request = payload.get("payload", {}).get("KYC_REQUEST", {})
	if kyc_request.get("id"):
		return kyc_request.get("id")

	digilocker_request = payload.get("payload", {}).get("DIGILOCKER_REQUEST", {})
	return digilocker_request.get("id")


def extract_reference_document(payload):
	kyc_request = payload.get("payload", {}).get("KYC_REQUEST", {})
	if kyc_request.get("reference_id"):
		return kyc_request.get("reference_id")

	digilocker_request = payload.get("payload", {}).get("DIGILOCKER_REQUEST", {})
	if digilocker_request.get("reference_id"):
		return digilocker_request.get("reference_id")

	digio_document = payload.get("payload", {}).get("document", {})
	return digio_document.get("file_name")


def load_json_document(content):
	if not content:
		return {}

	try:
		loaded = json.loads(content)
	except json.JSONDecodeError:
		return {"response": content}

	if isinstance(loaded, dict):
		return loaded

	return {"response": loaded}


def make_webhook_request_log(payload, headers, response, error=None, reference_document=None):
	log = frappe.get_doc(
		{
			"doctype": "Webhook Request Log",
			"reference_doctype": "Digio Request Log",
			"reference_document": reference_document,
			"url": frappe.request.path,
			"headers": frappe.as_json(headers),
			"data": frappe.as_json(payload),
			"response": frappe.as_json(response),
			"error": error,
		}
	)
	log.save(ignore_permissions=True)
	return log


@frappe.whitelist(allow_guest=True)
def handle_digio_webhook():
	raw_payload = frappe.request.get_data() or b"{}"
	headers = dict(frappe.request.headers or {})
	checksum_header = frappe.get_request_header(DIGIO_CHECKSUM_HEADER)
	processing_error = None

	try:
		matched_environment = validate_digio_webhook_checksum(raw_payload, checksum_header)
		payload = frappe.parse_json(raw_payload.decode("utf-8")) or {}
		linked_log = update_digio_request_log_from_webhook(payload)
		response = {
			"status": "accepted",
			"event": payload.get("event"),
			"environment": matched_environment,
		}
		make_webhook_request_log(
			payload,
			headers,
			response,
			reference_document=linked_log.name
			if linked_log
			else get_digio_request_log_name(extract_digio_entity_id(payload)),
		)
		return response
	except frappe.ValidationError:
		processing_error = frappe.get_traceback()
		frappe.local.response.http_status_code = 403
		response = {"status": "rejected", "reason": "invalid_webhook_signature"}
		make_webhook_request_log(
			{"raw_payload": raw_payload.decode("utf-8", errors="ignore")},
			headers,
			response,
			error=processing_error,
			reference_document=None,
		)
		return response
	except Exception:
		processing_error = frappe.get_traceback()
		payload = {}
		try:
			payload = frappe.parse_json(raw_payload.decode("utf-8")) or {}
		except Exception:
			payload = {"raw_payload": raw_payload.decode("utf-8", errors="ignore")}

		response = {"status": "accepted_with_error"}
		make_webhook_request_log(
			payload,
			headers,
			response,
			error=processing_error,
			reference_document=get_digio_request_log_name(extract_digio_entity_id(payload)),
		)
		return response


@frappe.whitelist()
def update_digio_settings(production_url, api_client_id, api_secret):
	doc = frappe.get_single("Digio Settings")
	doc.enable_production = 1
	doc.production_url = production_url
	doc.api_client_id = api_client_id
	doc.api_secret = api_secret
	doc.save()
