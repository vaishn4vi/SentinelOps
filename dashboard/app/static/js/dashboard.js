// SentinelOps — dashboard analytics (Chart.js)
(function () {
  "use strict";

  const script = document.getElementById("dashboardScript");
  const endpoint = script ? script.dataset.endpoint : "/dashboard/chart-data";
  const charts = {};

  const COLORS = {
    success: "#22c55e",
    failed: "#ef4444",
    rolled_back: "#f59e0b",
    in_progress: "#22d3ee",
    grid: "rgba(148, 163, 184, 0.08)",
    text: "#8a94a8",
  };

  if (typeof Chart === "undefined") {
    console.error("Chart.js failed to load");
    return;
  }

  Chart.defaults.color = COLORS.text;
  Chart.defaults.font.family = "Inter, system-ui, sans-serif";
  Chart.defaults.borderColor = COLORS.grid;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxWidth = 8;
  Chart.defaults.plugins.tooltip.backgroundColor = "#0e1420";
  Chart.defaults.plugins.tooltip.borderColor = "#232d42";
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.maintainAspectRatio = false;

  function formatDay(iso) {
    const d = new Date(iso + "T00:00:00Z");
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", timeZone: "UTC" });
  }

  function upsert(id, config) {
    const canvas = document.getElementById(id);
    if (!canvas) return;
    if (charts[id]) {
      charts[id].data = config.data;
      charts[id].update();
    } else {
      charts[id] = new Chart(canvas, config);
    }
  }

  function render(data) {
    const stackedScales = {
      x: { stacked: true, grid: { display: false } },
      y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } },
    };

    upsert("trendChart", {
      type: "bar",
      data: {
        labels: data.trend.labels.map(formatDay),
        datasets: [
          { label: "Success", data: data.trend.success, backgroundColor: COLORS.success, borderRadius: 4, maxBarThickness: 28 },
          { label: "Failed", data: data.trend.failed, backgroundColor: COLORS.failed, borderRadius: 4, maxBarThickness: 28 },
          { label: "Rolled back", data: data.trend.rolled_back, backgroundColor: COLORS.rolled_back, borderRadius: 4, maxBarThickness: 28 },
        ],
      },
      options: { scales: stackedScales, interaction: { mode: "index", intersect: false } },
    });

    const statusTotal = data.status.values.reduce((a, b) => a + b, 0);
    upsert("statusChart", {
      type: "doughnut",
      data: {
        labels: data.status.labels,
        datasets: [{
          data: statusTotal ? data.status.values : [1],
          backgroundColor: statusTotal
            ? [COLORS.success, COLORS.failed, COLORS.rolled_back, COLORS.in_progress]
            : ["#232d42"],
          borderColor: "#121826",
          borderWidth: 3,
          hoverOffset: 6,
        }],
      },
      options: {
        cutout: "68%",
        plugins: {
          legend: { position: "bottom" },
          tooltip: { enabled: statusTotal > 0 },
        },
      },
    });

    upsert("serviceChart", {
      type: "bar",
      data: {
        labels: data.services.labels,
        datasets: [
          { label: "Success", data: data.services.success, backgroundColor: COLORS.success, borderRadius: 4, maxBarThickness: 22 },
          { label: "Failed / rolled back", data: data.services.failed, backgroundColor: COLORS.failed, borderRadius: 4, maxBarThickness: 22 },
        ],
      },
      options: {
        indexAxis: "y",
        scales: {
          x: { stacked: true, beginAtZero: true, ticks: { precision: 0 } },
          y: { stacked: true, grid: { display: false } },
        },
      },
    });
  }

  function load() {
    return fetch(endpoint, { headers: { Accept: "application/json" }, credentials: "same-origin" })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(render)
      .catch(function (err) {
        console.error("Failed to load chart data:", err);
        document.querySelectorAll(".chart-box").forEach(function (box) {
          box.innerHTML = '<div class="empty-state"><i class="bi bi-exclamation-triangle"></i><p>Could not load analytics.</p></div>';
        });
      });
  }

  load();
  // Auto-refresh every 60s so new pipeline runs appear without reloading
  window.setInterval(load, 60000);

  const refresh = document.getElementById("refreshCharts");
  if (refresh) {
    refresh.addEventListener("click", function () {
      window.location.reload();
    });
  }
})();
