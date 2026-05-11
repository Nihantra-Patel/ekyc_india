// Digio Web SDK helper for Frappe Desk.
(function () {
	"use strict";

	let preparedState = null;
	let sdkLoadPromise = null;

	function normalizeBaseUrl(baseUrl) {
		return (baseUrl || "").replace(/\/+$/, "");
	}

	function getSubmitArgs(requestId, identifier, tokenId) {
		if (!requestId) {
			throw new Error("requestId is required");
		}
		if (!identifier) {
			throw new Error("identifier is required");
		}
		if (tokenId) {
			return [requestId, identifier, tokenId];
		}
		return [requestId, identifier];
	}

	function loadSdk(baseUrlOrSdkUrl) {
		const input = normalizeBaseUrl(baseUrlOrSdkUrl);
		const sdkUrl = /\/digio\.js$/i.test(input)
			? input
			: `${input}/sdk/v11/digio.js`;

		if (window.Digio) {
			return Promise.resolve();
		}

		if (sdkLoadPromise) {
			return sdkLoadPromise;
		}

		sdkLoadPromise = new Promise((resolve, reject) => {
			const script = document.createElement("script");
			script.type = "text/javascript";
			script.src = sdkUrl;
			script.async = true;
			script.onload = () => resolve();
			script.onerror = () => reject(new Error(`Unable to load Digio SDK from ${sdkUrl}`));
			document.head.appendChild(script);
		});

		return sdkLoadPromise;
	}

	function getSdkConfig() {
		return frappe
			.call({
				method: "ekyc_india.ekyc_india.doctype.digio_settings.digio_settings.get_digio_sdk_config",
			})
			.then((r) => r.message || {});
	}

	function createRequest(args) {
		return frappe
			.call({
				method: "ekyc_india.ekyc_india.doctype.digio_settings.digio_settings.create_ekyc_request_for_sdk",
				args: {
					identifier: args.identifier,
					customer_name: args.customer_name,
					reference_id: args.reference_id,
					template_name: args.template_name,
					doctype: args.doctype,
				},
			})
			.then((r) => r.message || {});
	}

	async function prepare(options) {
		const sdkConfig = await getSdkConfig();
		await loadSdk(sdkConfig.sdk_url || sdkConfig.sdk_base_url || sdkConfig.base_url);

		preparedState = {
			sdkConfig,
			options: options || {},
		};

		return preparedState;
	}

	function getDigioOptions(overrideOptions) {
		if (!preparedState) {
			throw new Error("Digio SDK is not prepared. Call prepare() first.");
		}

		if (!window.Digio) {
			throw new Error("Digio SDK is not available in window.");
		}

		const resolvedOptions = Object.assign({}, preparedState.options, overrideOptions || {});
		const digioOptions = {
			environment: resolvedOptions.environment || preparedState.sdkConfig.environment,
			callback: resolvedOptions.callback || function () {},
			logo: resolvedOptions.logo,
			theme: resolvedOptions.theme,
			event_listener: resolvedOptions.event_listener,
		};

		if (typeof resolvedOptions.is_iframe === "boolean") {
			digioOptions.is_iframe = resolvedOptions.is_iframe;
		}

		if (typeof resolvedOptions.is_redirection_approach === "boolean") {
			digioOptions.is_redirection_approach = resolvedOptions.is_redirection_approach;
		}

		if (resolvedOptions.redirect_url) {
			digioOptions.redirect_url = resolvedOptions.redirect_url;
		}

		return digioOptions;
	}

	function begin(overrideOptions) {
		const digio = new window.Digio(getDigioOptions(overrideOptions));
		digio.init();
		return digio;
	}

	function open(submission, overrideOptions) {
		const digio = begin(overrideOptions);

		digio.submit.apply(
			digio,
			getSubmitArgs(submission.request_id, submission.identifier, submission.token_id)
		);
		return digio;
	}

	async function createRequestAndSubmit(digio, createArgs) {
		const payload = await createRequest(createArgs || {});
		const submission = {
			request_id: payload.request_id,
			identifier: payload.identifier || (createArgs && createArgs.identifier),
			token_id: payload.token_id,
		};

		digio.submit.apply(
			digio,
			getSubmitArgs(submission.request_id, submission.identifier, submission.token_id)
		);

		return { payload, digio };
	}

	async function createRequestAndOpen(createArgs, overrideOptions) {
		const digio = begin(overrideOptions);
		try {
			return await createRequestAndSubmit(digio, createArgs);
		} catch (error) {
			if (digio && typeof digio.cancel === "function") {
				digio.cancel();
			}
			throw error;
		}
	}

	window.ekycIndiaDigioSdk = {
		prepare,
		begin,
		open,
		createRequest,
		createRequestAndSubmit,
		createRequestAndOpen,
		getSdkConfig,
	};
})();
