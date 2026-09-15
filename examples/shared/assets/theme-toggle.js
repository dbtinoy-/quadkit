/* Quadkit example fleet — shared light/dark theme toggle.
 *
 * Served by every demo at /static/theme-toggle.js. Two responsibilities:
 *
 * 1. Applied synchronously, inline, in <head> (before tokens.css/style.css
 *    load) via the tiny bootstrap below — sets [data-theme] on <html> from
 *    localStorage (falling back to the OS's prefers-color-scheme) so there
 *    is no flash of the wrong theme on load.
 * 2. Loaded as a normal <script> near the end of <body> — wires up every
 *    element carrying [data-theme-toggle] to flip the theme and persist the
 *    choice, and keeps multiple toggle buttons (if a page has more than
 *    one) in sync.
 *
 * Usage in a view:
 *   <script>(function(){var t=localStorage.getItem("quadkit-theme")||
 *     (matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light");
 *     document.documentElement.setAttribute("data-theme",t);})();</script>
 *   ...
 *   <button type="button" data-theme-toggle aria-label="Toggle dark mode">🌓</button>
 *   ...
 *   <script src="/static/theme-toggle.js"></script>
 */
"use strict";

(function () {
  var STORAGE_KEY = "quadkit-theme";

  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
      btn.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
      btn.textContent = theme === "dark" ? "☀️" : "🌙";
    });
  }

  function toggleTheme() {
    var next = currentTheme() === "dark" ? "light" : "dark";
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch (err) {
      /* localStorage unavailable (private mode, etc.) — theme still flips for this load */
    }
    applyTheme(next);
  }

  document.addEventListener("DOMContentLoaded", function () {
    applyTheme(currentTheme());
    document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
      btn.addEventListener("click", toggleTheme);
    });
  });
})();
