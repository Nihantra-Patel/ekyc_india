// Copyright (c) 2025, hello@frappe.io and contributors
// For license information, please see license.txt

frappe.ui.form.on("Digio Settings", {
	refresh: function (frm) {
		$.each(frm.doc.documents || [], function (i, row) {
			frm.script_manager.trigger("document_type", row.doctype, row.name);
		});
	},
});

frappe.ui.form.on("e-Signature Document", {
	document_type: function (frm, cdt, cdn) {
		request_recipient_by_document_field(frm, cdt, cdn);
	},
	send_request_via: function (frm, cdt, cdn) {
		request_recipient_by_document_field(frm, cdt, cdn);
	},
});

function request_recipient_by_document_field(frm, cdt, cdn) {
	let row = locals[cdt][cdn];

	if (!row.document_type) return;

	frappe.model.with_doctype(row.document_type, function () {
		let fields = frappe.get_doc("DocType", row.document_type).fields;
		let receiver_fields = [];

		let get_select_options = function (df, parent_field) {
			let select_value = parent_field ? df.fieldname + "," + parent_field : df.fieldname;
			return select_value;
		};

		let get_receiver_fields = function (fields, is_extra_receiver_field) {
			let is_receiver_field = function (df) {
				return (
					is_extra_receiver_field(df) ||
					(df.options == "User" && df.fieldtype == "Link") ||
					(df.options == "Customer" && df.fieldtype == "Link")
				);
			};

			let extract_receiver_field = function (df) {
				if (frappe.model.table_fields.includes(df.fieldtype)) {
					let child_fields = frappe.get_doc("DocType", df.options).fields;
					return $.map(child_fields, function (cdf) {
						return is_receiver_field(cdf)
							? get_select_options(cdf, df.fieldname)
							: null;
					});
				} else {
					return is_receiver_field(df) ? get_select_options(df) : null;
				}
			};
			return $.map(fields, extract_receiver_field);
		};

		let receiver_fields_list = [];

		if (row.send_request_via === "Email") {
			receiver_fields_list = get_receiver_fields(fields, function (df) {
				return (
					df.fieldtype == "Data" &&
					df.fieldname &&
					df.fieldname.toLowerCase().includes("email")
				);
			});
		} else if (["Mobile"].includes(row.send_request_via)) {
			receiver_fields_list = get_receiver_fields(fields, function (df) {
				return (
					df.fieldtype == "Data" &&
					df.fieldname &&
					(df.fieldname.toLowerCase().includes("mobile") ||
						df.fieldname.toLowerCase().includes("phone"))
				);
			});
		}

		frm.fields_dict["documents"].grid.update_docfield_property(
			"request_recipient_by_document_field",
			"options",
			["", "owner"].concat(receiver_fields_list),
			cdn
		);
	});
}
