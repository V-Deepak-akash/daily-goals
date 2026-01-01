function startTask(id) {
  const time = prompt("Enter start time (HH:MM)");
  if (!time) return;

  fetch(`/task/start/${id}`, {
    method: "POST",
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ time })
  }).then(() => location.reload());
}

function completeTask(id) {
  const time = prompt("Enter end time (HH:MM)");
  if (!time) return;

  fetch(`/task/complete/${id}`, {
    method: "POST",
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ time })
  }).then(() => location.reload());
}