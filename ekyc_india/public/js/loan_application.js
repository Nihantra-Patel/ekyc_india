// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

// Adds the "Generate KFS" (Key Facts Statement) action to the Loan Application
// form. Shipped from the ekyc_india app so the Lending app is not modified.

frappe.ui.form.on("Loan Application", {
	generate_kfs_button: function (frm) {
		if (frm.doc.__islocal) {
			frappe.msgprint(__("Please save the Loan Application before generating the KFS."));
			return;
		}
		frappe.call({
			method: "ekyc_india.kfs.generate_kfs",
			args: { loan_application: frm.doc.name },
			freeze: true,
			freeze_message: __("Generating Key Facts Statement..."),
			callback: function () {
				frappe.show_alert({
					message: __("Key Facts Statement generated"),
					indicator: "green",
				});
				frm.reload_doc();
			},
		});
	},
});
