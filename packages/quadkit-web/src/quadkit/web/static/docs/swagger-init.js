/*
 * quadkit — Swagger UI boot script (vendored assets mode).
 *
 * Reads the OpenAPI URL from a data attribute on the mount point so the
 * docs page needs no inline <script>, which keeps the default CSP free of
 * 'unsafe-inline' (plans/09172026 H-03). Loaded after swagger-ui-bundle.js
 * and swagger-ui-standalone-preset.js, both of which are plain synchronous
 * <script src> tags placed before this file at the end of <body>.
 */
(function () {
    "use strict";

    var mount = document.getElementById("swagger-ui");
    if (!mount || typeof window.SwaggerUIBundle !== "function") {
        return;
    }

    var openapiUrl = mount.getAttribute("data-openapi-url");
    if (!openapiUrl) {
        return;
    }

    window.ui = window.SwaggerUIBundle({
        url: openapiUrl,
        dom_id: "#swagger-ui",
        deepLinking: true,
        presets: [
            window.SwaggerUIBundle.presets.apis,
            window.SwaggerUIStandalonePreset,
        ],
        plugins: [window.SwaggerUIBundle.plugins.DownloadUrl],
        layout: "StandaloneLayout",
    });
})();
