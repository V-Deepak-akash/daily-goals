let currentTask = null;

function closeAll() {
  document.querySelectorAll(".modal").forEach(m => m.classList.add("hidden"));
}

function openStart(id) {
  currentTask = id;
  document.getElementById("startModal").classList.remove("hidden");
}

function openComplete(id) {
  currentTask = id;
  document.getElementById("completeModal").classList.remove("hidden");
}

function openIncomplete(id) {
  currentTask = id;
  document.getElementById("incompleteModal").classList.remove("hidden");
}

function openCancel(id) {
  currentTask = id;
  document.getElementById("cancelModal").classList.remove("hidden");
}

/* CONFIRM ACTIONS */

function confirmStart() {
  fetch(`/task/start/${currentTask}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ time: startTime.value })
  }).then(() => location.reload());
}

function confirmComplete() {
  fetch(`/task/complete/${currentTask}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ time: completeTime.value })
  }).then(() => location.reload());
}

function confirmIncomplete() {
  fetch(`/task/incomplete/${currentTask}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: incompleteReason.value })
  }).then(() => location.reload());
}

function confirmCancel() {
  fetch(`/task/cancel/${currentTask}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      reason: cancelReason.value,
      comment: cancelComment.value
    })
  }).then(() => location.reload());
}
