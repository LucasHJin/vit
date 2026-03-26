/**
 * CSInterface.js — Adobe CEP CSInterface Library (v11.2)
 *
 * Minimal shim providing the CSInterface API surface. The real __adobe_cep__
 * native object is injected by the CEP runtime when running inside Premiere.
 *
 * For the full library, download from:
 *   https://github.com/AdobeDocs/CEP-Resources/blob/master/CEP_11.x/CSInterface.js
 * and replace this file.
 *
 * This shim is sufficient for production use because all methods delegate
 * to __adobe_cep__ which is always present inside Premiere.
 */

/* jshint ignore:start */

var SystemPath = {
    USER_DATA: "userData",
    COMMON_FILES: "commonFiles",
    MY_DOCUMENTS: "myDocuments",
    APPLICATION: "application",
    EXTENSION: "extension",
    HOST_APPLICATION: "hostApplication"
};

function CSInterface() {}

/**
 * Evaluate an ExtendScript expression in the host application.
 */
CSInterface.prototype.evalScript = function (script, callback) {
    if (typeof __adobe_cep__ !== "undefined") {
        var result = __adobe_cep__.evalScript(script);
        if (callback && typeof callback === "function") {
            callback(result);
        }
    } else {
        // Development fallback — window.cep_node may be available
        if (callback && typeof callback === "function") {
            callback("EvalScript error.");
        }
    }
};

/**
 * Get a system path.
 */
CSInterface.prototype.getSystemPath = function (pathType) {
    if (typeof __adobe_cep__ !== "undefined") {
        return __adobe_cep__.getSystemPath(pathType);
    }
    // Development fallback
    if (pathType === SystemPath.EXTENSION) {
        // Try to determine from script location
        if (typeof __dirname !== "undefined") {
            return __dirname;
        }
        return ".";
    }
    return "";
};

/**
 * Register an event listener.
 */
CSInterface.prototype.addEventListener = function (type, listener, obj) {
    if (typeof __adobe_cep__ !== "undefined" && __adobe_cep__.addEventListener) {
        __adobe_cep__.addEventListener(type, listener, obj);
    }
};

/**
 * Remove an event listener.
 */
CSInterface.prototype.removeEventListener = function (type, listener, obj) {
    if (typeof __adobe_cep__ !== "undefined" && __adobe_cep__.removeEventListener) {
        __adobe_cep__.removeEventListener(type, listener, obj);
    }
};

/**
 * Dispatch an event.
 */
CSInterface.prototype.dispatchEvent = function (event) {
    if (typeof __adobe_cep__ !== "undefined" && __adobe_cep__.dispatchEvent) {
        __adobe_cep__.dispatchEvent(event);
    }
};

/**
 * Close this extension.
 */
CSInterface.prototype.closeExtension = function () {
    if (typeof __adobe_cep__ !== "undefined" && __adobe_cep__.closeExtension) {
        __adobe_cep__.closeExtension();
    }
};

/**
 * Get the host environment info.
 */
CSInterface.prototype.getHostEnvironment = function () {
    if (typeof __adobe_cep__ !== "undefined" && __adobe_cep__.getHostEnvironment) {
        var env = __adobe_cep__.getHostEnvironment();
        return typeof env === "string" ? JSON.parse(env) : env;
    }
    return {
        appName: "PPRO",
        appVersion: "99.0",
        appLocale: "en_US"
    };
};

/**
 * Request to open a URL in the default browser.
 */
CSInterface.prototype.openURLInDefaultBrowser = function (url) {
    if (typeof __adobe_cep__ !== "undefined" && __adobe_cep__.openURLInDefaultBrowser) {
        __adobe_cep__.openURLInDefaultBrowser(url);
    }
};

/**
 * Get the current API version.
 */
CSInterface.prototype.getCurrentApiVersion = function () {
    return { major: 11, minor: 2, micro: 0 };
};

/* jshint ignore:end */
