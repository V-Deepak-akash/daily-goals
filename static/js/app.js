const csrfToken = document
  .querySelector('meta[name="csrf-token"]')
  ?.getAttribute("content");

let currentTask = null;
let friendToRemove = null;
let removeFollowerId = null;

let state = {
  user: null,
  tasks: [],
  heatmap: [],
  leaderboard: []
};

async function loadDashboard() {
  const res = await fetch("/api/dashboard");
  const data = await res.json();
  state.user = data.user;
  state.tasks = data.tasks || [];
  state.heatmap = data.heatmap || [];
  state.leaderboard = data.leaderboard || [];
  renderDashboard();
}

function renderDashboard() {
  if (!state || !state.user) return;

  document.getElementById("greeting").innerText =
    `Hi ${state.user.username} 👋`;

  document.getElementById("xpValue").innerText = state.user.xp;

  const list = document.getElementById("taskList");
  list.innerHTML = "";

  state.tasks.forEach(t => {
    list.innerHTML += `
      <div class="task">
        <h3>${t.title}</h3>
        <p>${t.desc || ""}</p>
        <small>🕒 ${t.start} – ${t.end}</small>
        ${renderTaskActions(t)}
      </div>
    `;
  });
  renderLeaderboard();
}

function renderTaskActions(t) {
  if (t.status === "pending")
    return `<button onclick="openStart(${t.id})">Start</button>`;
  if (t.status === "active")
    return `<button onclick="completeTask(${t.id})">Complete</button>`;
  if (t.status === "completed")
    return `✅ Completed`;
  return "";
}

function completeTask(id) {
  currentTask = id;
  openModal("completeModal");
}

function openModal(id) {
  document.body.style.overflow = "hidden";
  document.querySelectorAll(".modal").forEach(m => m.classList.add("hidden"));
  document.getElementById(id).classList.remove("hidden");
}

function closeAll() {
  document.body.style.overflow = "";
  document.querySelectorAll(".modal").forEach(m => m.classList.add("hidden"));
}

function openStart(id) {
  currentTask = id;
  openModal("startModal");
}

function openComplete(id) {
  currentTask = id;
  openModal("completeModal");
}

function openIncomplete(id) {
  currentTask = id;
  openModal("incompleteModal");
}

function openCancel(id) {
  currentTask = id;
  openModal("cancelModal");
}

/* CONFIRM ACTIONS */

function confirmStart() {
  fetch(`/task/start/${currentTask}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken
    },
    body: JSON.stringify({ time: startTime.value })
  }).then(() => {
    closeAll();
    loadDashboard();
  });
}

function confirmComplete() {
  fetch(`/task/complete/${currentTask}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken
    },
    body: JSON.stringify({ time: completeTime.value })
  })
    .then(r => r.json())
    .then(d => {
      if (d.ok) {
        closeAll();
        loadDashboard();   // ✅ ADD THIS

        if (d.xp !== undefined) {
          const xpEl = document.getElementById("xpValue");
          const currentXP = parseInt(xpEl.innerText, 10);
          animateNumber(xpEl, currentXP, d.xp);
        }

        showToast("⭐ Task completed");
      }
    });
}

function confirmIncomplete() {
  fetch(`/task/incomplete/${currentTask}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken
    },
    body: JSON.stringify({ reason: incompleteReason.value })
  }).then(() => {
    closeAll();
    loadDashboard();
  });
}

function confirmCancel() {
  fetch(`/task/cancel/${currentTask}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken
    },
    body: JSON.stringify({
      reason: cancelReason.value,
      comment: cancelComment.value
    })
  }).then(() => {
    closeAll();
    loadDashboard();
  });
}

function openRemoveFriend(id) {
  friendToRemove = id;
  document.getElementById("removeFriendModal").classList.remove("hidden");
}

function confirmRemoveFriend() {
  fetch(`/friend/delete/${friendToRemove}`, {
    method: "POST",
    headers: {
      "X-CSRFToken": csrfToken
    }
  }).then(() => {
    closeAll();
    loadDashboard();
  });
}

function openNotifications() {
  document.getElementById("notifModal").classList.remove("hidden");
}

function acceptRequest(id) {
  fetch(`/friend/accept/${id}`, {
    method: "POST",
    headers: { "X-CSRFToken": csrfToken }
  })
    .then(r => r.json())
    .then(d => {
      if (d.ok) {
        document.querySelector(`[data-notif="${id}"]`)?.remove();
        updateBell();
        showToast("✔ Friend added");
      }
    });
}

function declineRequest(id) {
  fetch(`/friend/decline/${id}`, {
    method: "POST",
    headers: {
      "X-CSRFToken": csrfToken
    }
  })
    .then(() => {
      closeAll();
      loadDashboard();
    });
}

function toggleGlobalPrivacy(el) {
  fetch("/privacy/global", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken
    },
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

function confirmRemoveFollower(id) {
  removeFollowerId = id;
  document.getElementById("removeFriendModal").classList.remove("hidden");
}

function confirmRemoveFollowerFinal() {
  fetch(`/follower/remove/${removeFollowerId}`, {
    method: "POST",
    headers: {
      "X-CSRFToken": csrfToken
    }
  })
    .then(() => {
      closeAll();
      loadDashboard();
    });
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

function showToast(message) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.innerText = message;
  document.body.appendChild(toast);

  setTimeout(() => toast.remove(), 2500);
}

function addFriend() {
  const input = document.getElementById("friendUsername");
  const username = input.value.trim();
  if (!username) return;

  fetch("/add-friend", {
    method: "POST",
    headers: { "X-CSRFToken": csrfToken },
    body: new URLSearchParams({ username })
  })
    .then(r => r.json())
    .then(d => {
      if (!d.ok) {
        showToast(
          d.error === "requested"
            ? "⏳ Request already sent"
            : d.error === "following"
              ? "✔ Already friends"
              : "❌ Error"
        );
      } else {
        showToast("📨 Friend request sent");
        input.value = "";
      }
    });
}

function updateBell() {
  const count = document.querySelectorAll("#notifModal .task").length;
  const dot = document.getElementById("notifDot");
  if (!dot) return;
  dot.classList.toggle("hidden", count === 0);
}

const addFriendDebounced = debounce(addFriend, 700);

function debounce(fn, delay = 600) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

function animateNumber(el, from, to, duration = 700) {
  const start = performance.now();

  function frame(now) {
    const progress = Math.min((now - start) / duration, 1);
    const value = Math.floor(from + (to - from) * progress);
    el.innerText = value;
    if (progress < 1) requestAnimationFrame(frame);
  }

  requestAnimationFrame(frame);
}

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("taskList")) {
    loadDashboard();
  }
});

function renderHeatmap() {
  const box = document.getElementById("heatmap");
  if (!box) return;

  box.innerHTML = "";

  state.heatmap.forEach(score => {
    let level = 0;
    if (score >= 80) level = 4;
    else if (score >= 60) level = 3;
    else if (score >= 40) level = 2;
    else if (score > 0) level = 1;

    const day = document.createElement("div");
    day.className = `day level-${level}`;
    box.appendChild(day);
  });
}

function renderLeaderboard() {
  const box = document.getElementById("leaderboard");
  if (!box) return;

  box.innerHTML = "";

  state.leaderboard.forEach((u, i) => {
    box.innerHTML += `
      <div class="leaderboard-row ${u.is_me ? "me" : ""}">
        <strong>${i + 1}. ${u.name}</strong>
        <span>🔥 ${u.streak}</span>
        <span>⭐ ${u.score}%</span>
      </div>
    `;
  });
}
