const API = "/api";
let workflows = [];
let runs = [];
let recordedSteps = [];
let recording = false;
let toastTimer;

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function escapeHtml(value) {
  return String(value == null ? "" : value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[char]));
}

async function request(path, options) {
  const response = await fetch(API + path, Object.assign({
    headers: { "Content-Type": "application/json" }
  }, options || {}));
  if (!response.ok) {
    let message = "Something went wrong";
    try { const body = await response.json(); message = body.detail || message; } catch (_) {}
    throw new Error(message);
  }
  if (response.status === 204) return null;
  return response.json();
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2600);
}

function goTo(view) {
  $$(".view").forEach((section) => section.classList.remove("active-view"));
  const target = $("#view-" + view);
  if (target) target.classList.add("active-view");
  $$(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  const labels = { overview: "Overview", workflows: "My workflows", builder: "Builder", runs: "Run history" };
  $("#crumb-current").textContent = labels[view] || "Overview";
  if (view === "runs") loadRuns();
  if (view === "workflows") loadWorkflows();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function workflowSymbol(name) {
  const first = (name || "W").trim().charAt(0).toUpperCase();
  return first || "W";
}

function workflowRow(item, compact) {
  const steps = Array.isArray(item.steps) ? item.steps.length : 0;
  return '<div class="workflow-row">' +
    '<div class="workflow-symbol">' + escapeHtml(workflowSymbol(item.name)) + '</div>' +
    '<div class="workflow-info"><strong>' + escapeHtml(item.name) + '</strong><small>' + escapeHtml(item.trigger || "Manual") + ' · ' + steps + ' steps</small></div>' +
    '<div class="workflow-meta">' + new Date(item.updated_at).toLocaleDateString() + '</div>' +
    '<button class="run-mini" data-run="' + item.id + '">▶ Run</button>' +
    (compact ? '' : '<button class="run-mini" data-delete="' + item.id + '" title="Delete workflow">×</button>') +
    '</div>';
}

async function loadWorkflows() {
  try {
    workflows = await request("/workflows");
    $("#workflow-count").textContent = workflows.length;
    $("#stat-workflows").textContent = workflows.length;
    $("#all-count").textContent = workflows.length + (workflows.length === 1 ? " workflow" : " workflows");
    $("#recent-workflows").innerHTML = workflows.length
      ? workflows.slice(0, 4).map((item) => workflowRow(item, true)).join("")
      : '<div class="empty-state">No workflows yet. Create your first one in the Builder.</div>';
    $("#all-workflows").innerHTML = workflows.length
      ? workflows.map((item) => workflowRow(item, false)).join("")
      : '<div class="empty-state">Your workspace is ready. Create a workflow to get started.</div>';
    loadRuns(false);
  } catch (error) {
    $("#recent-workflows").innerHTML = '<div class="empty-state">Could not load workflows. ' + escapeHtml(error.message) + '</div>';
  }
}

async function loadRuns(updateList) {
  try {
    runs = await request("/runs");
    const success = runs.filter((run) => run.status === "success").length;
    $("#stat-runs").textContent = success;
    $("#stat-success").textContent = runs.length ? Math.round(success / runs.length * 100) + "%" : "—";
    if (updateList === false) return;
    $("#runs-list").innerHTML = runs.length ? runs.map((run) =>
      '<div class="run-row"><span class="run-name">' + escapeHtml(run.workflow_name) + '</span>' +
      '<span class="run-status">' + escapeHtml(run.status) + '</span>' +
      '<span class="run-duration">' + (run.duration_ms / 1000).toFixed(1) + 's</span>' +
      '<span class="run-date">' + new Date(run.created_at).toLocaleString() + '</span></div>'
    ).join("") : '<div class="empty-state">No runs yet. Run one of your workflows to see activity here.</div>';
  } catch (error) {
    if (updateList !== false) $("#runs-list").innerHTML = '<div class="empty-state">Could not load run history.</div>';
  }
}

async function runWorkflow(id) {
  try {
    const result = await request("/workflows/" + id + "/run", { method: "POST" });
    showToast("Demo run completed successfully.");
    await loadWorkflows();
    await loadRuns(true);
  } catch (error) {
    showToast(error.message);
  }
}

function renderSteps() {
  $("#step-counter").textContent = recordedSteps.length + (recordedSteps.length === 1 ? " step" : " steps");
  if (!recordedSteps.length) {
    $("#recorded-steps").innerHTML = '<div class="empty-steps"><div class="empty-steps-icon">⌁</div><strong>No steps yet</strong><span>Start recording and interact with the demo page.</span></div>';
    return;
  }
  $("#recorded-steps").innerHTML = recordedSteps.map((step, index) =>
    '<div class="step-row"><span class="step-number">' + (index + 1) + '</span>' +
    '<div class="step-text"><strong>' + escapeHtml(step.label) + '</strong><small>' + escapeHtml(step.detail || step.type) + '</small></div>' +
    '<button class="step-remove" data-remove="' + index + '" aria-label="Remove step">×</button></div>'
  ).join("");
}

function addStep(type, label, detail) {
  if (!recording) return;
  recordedSteps.push({ type: type, label: label, detail: detail });
  renderSteps();
}

function setRecording(next) {
  recording = next;
  $("#record-toggle").classList.toggle("recording", recording);
  $("#record-toggle").textContent = recording ? "■ Stop recording" : "● Start recording";
  $("#recorder-pulse").classList.toggle("recording", recording);
  $("#recorder-state").textContent = recording ? "Recording demo actions…" : "Recorder is idle";
  $("#recorder-hint").textContent = recording ? "Interact with the sample page on the left" : "Start recording to capture demo actions";
  if (recording) showToast("Recording started. Try the demo buttons.");
  else showToast("Recording stopped. Your steps are ready.");
}

async function saveWorkflow() {
  const name = $("#workflow-name").value.trim();
  if (!name) { showToast("Please enter a workflow name."); return; }
  if (!recordedSteps.length) { showToast("Record at least one demo action first."); return; }
  try {
    await request("/workflows", {
      method: "POST",
      body: JSON.stringify({
        name: name,
        description: $("#workflow-description").value.trim(),
        trigger: "Manual",
        steps: recordedSteps
      })
    });
    recordedSteps = [];
    renderSteps();
    $("#workflow-name").value = "My first workflow";
    $("#workflow-description").value = "";
    setRecording(false);
    await loadWorkflows();
    goTo("workflows");
    showToast("Workflow saved to your workspace.");
  } catch (error) {
    showToast("Could not save workflow: " + error.message);
  }
}

document.addEventListener("click", async (event) => {
  const nav = event.target.closest("[data-view]");
  if (nav) goTo(nav.dataset.view);
  const goto = event.target.closest("[data-goto]");
  if (goto) goTo(goto.dataset.goto);
  const run = event.target.closest("[data-run]");
  if (run) runWorkflow(run.dataset.run);
  const remove = event.target.closest("[data-delete]");
  if (remove) {
    if (!window.confirm("Delete this workflow?")) return;
    try {
      await request("/workflows/" + remove.dataset.delete, { method: "DELETE" });
      await loadWorkflows();
      showToast("Workflow deleted.");
    } catch (error) { showToast(error.message); }
  }
  const stepRemove = event.target.closest("[data-remove]");
  if (stepRemove) {
    recordedSteps.splice(Number(stepRemove.dataset.remove), 1);
    renderSteps();
  }
});

$("#new-workflow-top").addEventListener("click", () => goTo("builder"));
$("#record-toggle").addEventListener("click", () => setRecording(!recording));
$("#clear-steps").addEventListener("click", () => { recordedSteps = []; renderSteps(); });
$("#save-workflow").addEventListener("click", saveWorkflow);

$(".browser-content").addEventListener("click", (event) => {
  if (!recording) return;
  const button = event.target.closest("button");
  if (!button) return;
  addStep("click", "Click " + (button.textContent.trim() || "button"), "Demo page button");
});

$("#demo-note").addEventListener("change", (event) => {
  if (recording && event.target.value.trim()) {
    addStep("input", "Enter a test note", event.target.value.trim().slice(0, 70));
  }
});

$("#demo-status").addEventListener("click", () => {
  $("#demo-feedback").textContent = "Status checked — all systems operational.";
  $("#demo-feedback").style.color = "#239b78";
  showToast("Demo status: all systems operational.");
});

$("#demo-add-note").addEventListener("click", () => {
  const input = $("#demo-note");
  if (!input.value.trim()) { showToast("Type a test note first."); return; }
  $("#demo-feedback").textContent = "Note added to this demo page only.";
  $("#demo-feedback").style.color = "#239b78";
  input.value = "";
});

async function boot() {
  try {
    await request("/health");
    await loadWorkflows();
  } catch (error) {
    $("#recent-workflows").innerHTML = '<div class="empty-state">API connection unavailable. Please refresh in a moment.</div>';
  }
}
boot();