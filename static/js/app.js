function startTask(id) {
  fetch(`/task/start/${id}`, { method: "POST" })
    .then(() => location.reload());
}

function completeTask(id) {
  fetch(`/task/complete/${id}`, { method: "POST" })
    .then(() => location.reload());
}
