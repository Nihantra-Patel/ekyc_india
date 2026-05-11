<div align="center">
	<h2>eKYC India</h2>
	<p align="center">
		<p>Frappe app for identity verification and e-signing integrations in India</p>
	</p>
</div>

---

## Digio Integration

[Digio](https://www.digio.in/) is an Indian regulatory-compliant platform for Aadhaar-based identity verification (eKYC) and electronic signatures (eSign).

This app handles the complete two-way integration:

- **Frappe → Digio** — sends eKYC or eSign requests
- **Digio → Frappe** — receives webhook events and updates the request status automatically

The integration works with **any Frappe DocType** — not just Loan Applications.

### Digio Documentation

| Topic | Link |
|---|---|
| Environments (Sandbox / Production) | https://documentation.digio.in/digienvironments/ |
| eSign Webhook Events | https://documentation.digio.in/digisign/api_integration/webhooks/#webhook-events-for-digi-sign |
| eKYC Webhooks | https://documentation.digio.in/digistudio/integration/webhooks/ |
| Webhooks General Reference | https://documentation.digio.in/webhooks/ |

---

### Setup
- Go to **Digio Settings** in the Frappe desk to configure the integration.

**General Settings**
- Request Expiry In Days: How many days before an unanswered request expires on the Digio side.
- Generate Access Token: Returns a one-time token in the response (needed for Web SDK flows).
- Send Sign Link: Digio emails a direct signing link to the customer.
- Notify Customers: Digio sends email/SMS updates to the customer at each status change.

**Environment — Sandbox / Production**

Digio provides two environments. Use **Sandbox** for testing and **Production** for live transactions. Only one can be active at a time.

For each environment, fill in the URL and the API Client ID / Secret obtained from the Digio dashboard.

> Sandbox credentials must be requested directly from the Digio team.

<img width="5744" height="2052" alt="image" src="https://github.com/user-attachments/assets/ad253487-750c-454d-a807-4b1f6c8eb11b" />

<br>

**Enable e-Sign for Document**
- Document Type: The Frappe DocType to enable (e.g. Loan Application).
- Send Request: How the request is delivered to the customer — Email or Mobile.
- Request Recipient By Document Field: The field on the document that holds the customer's email or mobile number. The dropdown auto-fills with eligible fields from the selected DocType.

Example — Loan Application sent via email to the applicant:

<img width="5744" height="1692" alt="image" src="https://github.com/user-attachments/assets/76b8ba27-f33a-42c1-9ba8-a20e55ff19bd" />

---

### eKYC Flow

1. A workflow action or button on the document triggers an eKYC request.
2. Frappe sends the request to Digio using the Aadhaar / PAN / DigiLocker template.
3. The customer receives an email or SMS with a link to complete verification.
4. The customer completes Aadhaar / PAN / DigiLocker steps on the Digio-hosted page.
5. Digio verifies the details and sends status updates back to Frappe via webhooks.

### eSign Flow

1. A workflow action or button on the document triggers an eSign request.
2. Frappe generates a PDF of the document and sends it to Digio along with the signer details.
3. The customer receives an email with a signing link.
4. The customer opens the link and completes Aadhaar-based electronic signing.
5. Digio sends status updates back to Frappe via webhooks.

---

### Webhooks

Digio sends status updates to Frappe automatically after each customer action. The webhook URL to register in the Digio dashboard is:

```
https://<your-frappe-site>/api/method/ekyc_india.ekyc_india.doctype.digio_settings.digio_settings.handle_webhook
```
Please follow the steps of [Webhooks General Reference](https://documentation.digio.in/webhooks)

<img width="5760" height="2736" alt="image" src="https://github.com/user-attachments/assets/17d90beb-f885-4929-adb1-eb6412ec1a80" />


---

### Digio Request Log

Every request sent to Digio and every webhook received is logged in **Digio Request Log**. Each log entry shows:

- The Digio request ID
- Whether it is an eSign or eKYC request
- The current status
- Which Frappe document it is linked to
- The full response from Digio and the latest webhook payload

<img width="5760" height="2736" alt="image" src="https://github.com/user-attachments/assets/804f1337-b678-4700-827f-6e4f37b6ee37" />
