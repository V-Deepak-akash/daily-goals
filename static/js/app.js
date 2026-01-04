let currentTask = null;
let friendToRemove = null;

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

function openRemoveFriend(id) {
  friendToRemove = id;
  document.getElementById("removeFriendModal").classList.remove("hidden");
}

function confirmRemoveFriend() {
  fetch(`/friend/delete/${friendToRemove}`, { method: "POST" })
    .then(() => location.reload());
}

function openNotifications() {
  document.getElementById("notifModal").classList.remove("hidden");
}

function acceptRequest(id) {
  fetch(`/friend/accept/${id}`, { method: "POST" })
    .then(() => location.reload());
}

function declineRequest(id) {
  fetch(`/friend/decline/${id}`, { method: "POST" })
    .then(() => location.reload());
}

function toggleGlobalPrivacy(el) {
  fetch("/privacy/global", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      show_global: el.checked
    })
  })
    .then(r => r.json())
    .then(d => {
      if (!d.ok) {
        alert("Failed to update privacy");
        el.checked = !el.checked; // revert
      }
    })
    .catch(() => {
      alert("Network error");
      el.checked = !el.checked;
    });
}


function closeMsg() {
  document.getElementById("msgModal").remove();
}

function openFollowers() {
  fetch("/followers")
    .then(r => r.json())
    .then(data => {
      const box = document.getElementById("followersList");
      box.innerHTML = "";

      data.forEach(f => {
        box.innerHTML += `
          <div class="task">
            <strong>${f.username}</strong>
            ${f.following_back ? "<small>Following</small>" : ""}
            <button onclick="confirmRemoveFollower(${f.rel_id})">🗑</button>
          </div>
        `;
      });

      document.getElementById("followersModal").classList.remove("hidden");
    });
}

let removeFollowerId = null;

function confirmRemoveFollower(id) {
  removeFollowerId = id;
  document.getElementById("removeFriendModal").classList.remove("hidden");
}

function confirmRemoveFollowerFinal() {
  fetch(`/follower/remove/${removeFollowerId}`, { method: "POST" })
    .then(() => location.reload());
}

const meRow = document.querySelector(".leaderboard-row.me");

if (meRow) {
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        meRow.classList.remove("locked");
      } else {
        meRow.classList.add("locked");
      }
    });
  });

  observer.observe(meRow);
}
