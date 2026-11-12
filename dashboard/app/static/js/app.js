// SentinelOps — shared UI behaviour
(function () {
  "use strict";

  // Clickable table rows
  document.addEventListener("click", function (event) {
    const row = event.target.closest("tr.row-link");
    if (!row || event.target.closest("a, button, form, input, select")) return;
    window.location.href = row.dataset.href;
  });

  // Confirmation for destructive forms
  document.addEventListener("submit", function (event) {
    const form = event.target;
    if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
      event.preventDefault();
    }
  });

  // Auto-dismiss success / info alerts
  window.setTimeout(function () {
    document.querySelectorAll(".alert-success, .alert-info").forEach(function (el) {
      if (window.bootstrap) bootstrap.Alert.getOrCreateInstance(el).close();
    });
  }, 5000);
})();
