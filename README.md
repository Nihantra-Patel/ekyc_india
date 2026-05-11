<div align="center">
	<h2>eKYC India</h2>
	<p align="center">
		<p>Official frappe app for identity and compliance integrations</p>
	</p>
</div>

## Digio Integration

For doing KYC and e-Signing via Aadhar, users will have to enable Digio Integration

### Web SDK Integration (Frappe Desk)

This app now provides a full Digio Web SDK flow:

1. Create Digio request from server (secure API credentials stay on backend).
2. Load Digio JS SDK in Desk.
3. Start Digio popup from a user click.
4. Receive callback/event payload and update your document as needed.

### 1) Configure Digio Settings

Open `Digio Settings` and configure one mode:

- Production mode
  - Enable Production
  - Production URL: `https://app.digio.in`
  - API Client ID, API Secret
- Sandbox mode
  - Enable Sandbox
  - Sandbox URL: `https://ext.digio.in`
  - Sandbox API Client ID, Sandbox API Secret

### 2) Build assets and migrate

From your bench folder:

```bash
bench build
bench migrate
```

### 3) Use helper in a Client Script

The helper is exposed at `window.ekycIndiaDigioSdk`.

Example Client Script for any DocType:

```javascript
frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button("Start Digio KYC", async () => {
			try {
				// Prepare must run before opening popup.
				await window.ekycIndiaDigioSdk.prepare({
					logo: "https://www.mylogourl.com/image.jpeg",
					theme: {
						primaryColor: "#0a6eeb",
						secondaryColor: "#111111",
					},
					is_iframe: true,
					callback(response) {
						if (response && response.error_code) {
							frappe.msgprint(`Digio error: ${response.error_code}`);
							return;
						}
						frappe.msgprint("Digio flow completed successfully");
					},
					event_listener(event) {
						console.log("Digio event", event);
					},
				});

				// Creates request on backend and opens Digio popup.
				await window.ekycIndiaDigioSdk.createRequestAndOpen(
					{
						identifier: frm.doc.contact_email,
						customer_name: frm.doc.customer_name,
						reference_id: frm.doc.name,
						template_name: "DIGILOCKER_AADHAAR_PAN",
						doctype: frm.doc.doctype,
					},
					{}
				);
			} catch (e) {
				frappe.msgprint(e.message || "Unable to start Digio flow");
			}
		});
	},
});
```

### 4) Available backend APIs

- `ekyc_india.ekyc_india.doctype.digio_settings.digio_settings.get_digio_sdk_config`
  - returns `base_url`, `sdk_url`, `environment`
- `ekyc_india.ekyc_india.doctype.digio_settings.digio_settings.create_ekyc_request_for_sdk`
  - input: `identifier`, optional `customer_name`, `reference_id`, `template_name`
  - returns `request_id`, `identifier`, optional `token_id`, and raw response

### 5) Popup blocker note

Digio `init()` should be called from a user action (button click). The helper follows this pattern, but keep your launch flow inside click handlers.



## Credit Score Fetch
TBA
