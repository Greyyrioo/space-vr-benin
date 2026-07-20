// ============================================================================
// SpaceVR — admin.js
// Powers the private /admin control center: live booking table, stats,
// and the two-way support ticket hub.
// ============================================================================

(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", () => {
    loadBookings();
    loadTickets();
  });

  window.switchPanel = function (panelId, btn) {
    document.querySelectorAll(".admin-panel").forEach((p) => p.classList.remove("active"));
    document.getElementById(panelId).classList.add("active");
    document.querySelectorAll(".admin-nav button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
  };

  const STATUS_LABELS = {
    pending_payment: "Pending Payment",
    awaiting_verification: "Awaiting Verification",
    confirmed: "Confirmed",
    cancelled: "Cancelled",
  };

  const STATUS_COLORS = {
    pending_payment: "background: rgba(255,178,56,0.15); color:#ffb238; border:1px solid rgba(255,178,56,0.4);",
    awaiting_verification: "background: rgba(255,178,56,0.15); color:#ffb238; border:1px solid rgba(255,178,56,0.4);",
    confirmed: "background: rgba(46,230,166,0.12); color:#2ee6a6; border:1px solid rgba(46,230,166,0.4);",
    cancelled: "background: rgba(255,59,92,0.12); color:#ff3b5c; border:1px solid rgba(255,59,92,0.4);",
  };

  // --------------------------------------------------------------------
  // Bookings
  // --------------------------------------------------------------------

  window.loadBookings = async function () {
    try {
      const res = await fetch("/admin/api/bookings");
      if (res.status === 401 || res.redirected) {
        window.location.href = "/admin/login";
        return;
      }
      const data = await res.json();
      renderStats(data.stats);
      renderBookingsTable(data.bookings, "bookingsTableWrap");
      renderBookingsTable(data.bookings.slice(0, 6), "recentBookingsTableWrap");
      document.getElementById("bookingsCountBadge").textContent = data.stats.total_bookings;
    } catch (err) {
      showToast("Could not load bookings.", "error");
    }
  };

  function renderStats(stats) {
    document.getElementById("statTotalBookings").textContent = stats.total_bookings;
    document.getElementById("statRevenue").textContent = `₦${Number(stats.total_revenue || 0).toLocaleString()}`;
    document.getElementById("statAwaiting").textContent = stats.pending_verification;
    document.getElementById("statPendingPayment").textContent = stats.pending_payment;
  }

  function renderBookingsTable(bookings, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (bookings.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="icon">◍</div>
          <div>No bookings yet. New reservations will appear here in real time.</div>
        </div>
      `;
      return;
    }

    const rows = bookings
      .map((b) => {
        const drinksHtml =
          b.drinks && b.drinks.length > 0
            ? b.drinks.map((d) => `<span class="drink-line">${d.qty} × ${escapeHtml(d.name)}</span>`).join("")
            : "<span class=\"drink-line\">—</span>";

        const canConfirm = b.status === "awaiting_verification";
        const canCancel = b.status !== "cancelled" && b.status !== "confirmed";

        return `
          <tr>
            <td><span class="ref-tag">${b.ref_id}</span></td>
            <td>${escapeHtml(b.customer_name)}<br><span style="color:var(--text-faint); font-size:12px;">${escapeHtml(b.phone)} · ${escapeHtml(b.email)}</span></td>
            <td>${escapeHtml(b.zone_name)}</td>
            <td>${b.duration_min} min</td>
            <td>${escapeHtml(b.session_date)}<br><span style="color:var(--text-faint); font-size:12px;">${escapeHtml(b.time_slot)}</span></td>
            <td class="drinks-cell">${drinksHtml}</td>
            <td>₦${b.total_cost.toFixed(2)}</td>
            <td><span class="status-badge" style="${STATUS_COLORS[b.status] || ""}">${STATUS_LABELS[b.status] || b.status}</span></td>
            <td>
              <div class="row-actions">
                ${canConfirm ? `<button class="confirm-btn" onclick="confirmBooking('${b.ref_id}')">Confirm</button>` : ""}
                ${canCancel ? `<button class="cancel-btn" onclick="cancelBooking('${b.ref_id}')">Cancel</button>` : ""}
              </div>
            </td>
          </tr>
        `;
      })
      .join("");

    container.innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>Ref</th><th>Customer</th><th>Zone</th><th>Duration</th><th>Session</th>
            <th>Fuel Bar</th><th>Total</th><th>Status</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  }

  window.confirmBooking = async function (refId) {
    try {
      const res = await fetch(`/admin/api/bookings/${refId}/confirm`, { method: "POST" });
      const data = await res.json();
      if (data.success) {
        showToast(`Booking ${refId} confirmed — customer notified by email.`, "success");
        loadBookings();
      } else {
        showToast(data.error || "Could not confirm booking.", "error");
      }
    } catch (err) {
      showToast("Network error — please try again.", "error");
    }
  };

  window.cancelBooking = async function (refId) {
    if (!confirm(`Cancel booking ${refId}? This cannot be undone.`)) return;
    try {
      const res = await fetch(`/admin/api/bookings/${refId}/cancel`, { method: "POST" });
      const data = await res.json();
      if (data.success) {
        showToast(`Booking ${refId} cancelled.`, "success");
        loadBookings();
      } else {
        showToast(data.error || "Could not cancel booking.", "error");
      }
    } catch (err) {
      showToast("Network error — please try again.", "error");
    }
  };

  // --------------------------------------------------------------------
  // Support tickets
  // --------------------------------------------------------------------

  window.loadTickets = async function () {
    try {
      const res = await fetch("/admin/api/tickets");
      if (res.status === 401 || res.redirected) {
        window.location.href = "/admin/login";
        return;
      }
      const data = await res.json();
      renderTickets(data.tickets);
      document.getElementById("ticketsCountBadge").textContent = data.open_count;
      document.getElementById("statOpenTickets").textContent = data.open_count;
    } catch (err) {
      showToast("Could not load support tickets.", "error");
    }
  };

  function renderTickets(tickets) {
    const container = document.getElementById("ticketList");
    if (tickets.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="icon">✉</div>
          <div>No support tickets yet. Customer messages will appear here.</div>
        </div>
      `;
      return;
    }

    container.innerHTML = tickets
      .map((t) => {
        const isAnswered = t.status === "answered";
        return `
          <div class="ticket-card" data-ticket-id="${t.id}">
            <div class="ticket-top">
              <div>
                <div class="ticket-subject">${escapeHtml(t.subject)}</div>
                <div class="ticket-meta">${escapeHtml(t.name)} · ${escapeHtml(t.email)}${t.phone ? " · " + escapeHtml(t.phone) : ""}</div>
              </div>
              <span class="status-badge" style="${isAnswered ? STATUS_COLORS.confirmed : STATUS_COLORS.pending_payment}">
                ${isAnswered ? "Answered" : "Open"}
              </span>
            </div>
            <div class="ticket-message">${escapeHtml(t.message)}</div>

            ${
              isAnswered
                ? `<div class="existing-reply"><span class="reply-label">Your Reply</span>${escapeHtml(t.admin_reply)}</div>`
                : `
                  <div style="margin-top:14px;">
                    <button class="btn btn-ghost btn-small" onclick="toggleReplyBox(${t.id})">Write a Reply</button>
                  </div>
                  <div class="ticket-reply-box" id="replyBox-${t.id}">
                    <textarea id="replyText-${t.id}" placeholder="Type your response to the customer…"></textarea>
                    <button class="btn btn-primary btn-small" style="justify-self:start;" onclick="submitReply(${t.id})">Send Reply By Email</button>
                  </div>
                `
            }
          </div>
        `;
      })
      .join("");
  }

  window.toggleReplyBox = function (ticketId) {
    const box = document.getElementById(`replyBox-${ticketId}`);
    box.classList.toggle("active");
  };

  window.submitReply = async function (ticketId) {
    const textarea = document.getElementById(`replyText-${ticketId}`);
    const reply = textarea.value.trim();
    if (reply.length === 0) {
      showToast("Please write a reply before sending.", "error");
      return;
    }

    try {
      const res = await fetch(`/admin/api/tickets/${ticketId}/reply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reply }),
      });
      const data = await res.json();
      if (data.success) {
        showToast("Reply sent to customer's inbox.", "success");
        loadTickets();
      } else {
        showToast(data.error || "Could not send reply.", "error");
      }
    } catch (err) {
      showToast("Network error — please try again.", "error");
    }
  };

  // --------------------------------------------------------------------
  // Utilities
  // --------------------------------------------------------------------

  let toastTimeout = null;
  function showToast(message, type) {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.className = "toast show " + (type || "");
    clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => toast.classList.remove("show"), 4500);
  }
  window.showToast = showToast;

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str == null ? "" : String(str);
    return div.innerHTML;
  }
})();
