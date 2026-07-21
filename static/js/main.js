// ============================================================================
// SpaceVR — main.js
// Handles: zone modals, the Fuel Bar quantity selector, the booking form,
// the checkout / bank-transfer step, and the support contact form.
// ============================================================================

(function () {
  "use strict";

  const DATA = window.SPACEVR_DATA;

  // bookingState holds everything that needs to travel with the booking
  // payload: which zone was picked from a zone card, and how many of each
  // Fuel Bar item the user has selected.
  const bookingState = {
    zoneId: null,
    drinks: {}, // { item_id: qty }
  };

  document.addEventListener("DOMContentLoaded", () => {
    const yearEl = document.getElementById("year");
    if (yearEl) yearEl.textContent = new Date().getFullYear();

    const today = new Date().toISOString().split("T")[0];
    const dateInput = document.getElementById("bookingDate");
    if (dateInput) dateInput.min = today;

    wireBookingFormEvents();
    wireBookingFormSubmit();
    wireSupportForm();
    wireCheckout();
  });

  // --------------------------------------------------------------------
  // Modal helpers
  // --------------------------------------------------------------------

  window.closeModal = function (id) {
    document.getElementById(id).classList.remove("active");
    document.body.style.overflow = "";
  };

  function openModal(id) {
    document.getElementById(id).classList.add("active");
    document.body.style.overflow = "hidden";
  }

  // --------------------------------------------------------------------
  // Zone modal (game listing OR fuel bar menu)
  // --------------------------------------------------------------------

  window.openZoneModal = function (zoneId) {
    const zone = DATA.zones[zoneId];
    if (!zone) return;

    document.getElementById("zoneModalEyebrow").textContent =
      zoneId === "fuel-bar" ? "Fuel Bar Menu" : "Zone Briefing";
    document.getElementById("zoneModalTitle").textContent = zone.name;
    document.getElementById("zoneModalTagline").textContent = zone.tagline;

    const gameListEl = document.getElementById("zoneModalGames");
    const fuelContainerEl = document.getElementById("fuelMenuContainer");
    const primaryBtn = document.getElementById("zoneModalPrimaryBtn");

    if (zoneId === "fuel-bar") {
      gameListEl.style.display = "none";
      gameListEl.innerHTML = "";
      fuelContainerEl.style.display = "block";
      renderFuelMenu(fuelContainerEl);

      primaryBtn.textContent = "Add To Booking";
      primaryBtn.onclick = function () {
        closeModal("zoneModal");
        openBookingModal();
      };
    } else {
      fuelContainerEl.style.display = "none";
      fuelContainerEl.innerHTML = "";
        gameListEl.style.display = "grid";
        gameListEl.innerHTML = zone.games
                    .map(function(g) { return '<li style="cursor: pointer;" onclick="selectGameAndBook(\'' + zoneId + '\', \'' + escapeHtml(g) + '\')">▸ ' + escapeHtml(g) + '</li>'; })
        .join("");
                gameListEl.onclick = function (e) {
            const li = e.target.closest("li");
            if (li) {
                selectGameAndBook(li.dataset.zone, li.dataset.game);
            }
        };

        primaryBtn.textContent = "Book This Zone";
        primaryBtn.onclick = function () {
            selectZoneAndBook(zoneId);
        };
   
    openModal("zoneModal");
  };
window.selectZoneAndBook = function (zoneId) {
    bookingState.zoneId = zoneId;
    closeModal("zoneModal");
    openBookingModal();

    const zoneSelect = document.getElementById("zone_select") || document.querySelector("select[name='zone_id']");
    if (zoneSelect) {
        zoneSelect.value = zoneId;
        zoneSelect.dispatchEvent(new Event("change"));
    }
};

window.selectGameAndBook = function (zoneId, gameName) {
    selectZoneAndBook(zoneId);

    const gameSelect = document.getElementById("game_select") || document.querySelector("select[name='game']");
    if (gameSelect) {
        gameSelect.value = gameName;
    }
};

  function renderFuelMenu(container) {
    const menu = DATA.fuelBarMenu;
    const rows = Object.keys(menu)
      .map((itemId) => {
        const item = menu[itemId];
        const qty = bookingState.drinks[itemId] || 0;
        return `
          <div class="fuel-item" data-item-id="${itemId}">
            <div class="fuel-item-info">
              <div class="fuel-name">${escapeHtml(item.name)}</div>
              <div class="fuel-price">₦${item.price.toFixed(2)} each</div>
            </div>
            <div class="qty-control">
              <button type="button" class="qty-btn" data-action="dec">−</button>
              <span class="qty-value">${qty}</span>
              <button type="button" class="qty-btn" data-action="inc">+</button>
            </div>
          </div>
        `;
      })
      .join("");

    container.innerHTML = `
      <div class="fuel-menu">${rows}</div>
      <div class="fuel-summary">
        <span>Fuel Bar subtotal</span>
        <span class="fuel-total" id="fuelSubtotal">$0.00</span>
      </div>
    `;

    container.querySelectorAll(".fuel-item").forEach((rowEl) => {
      const itemId = rowEl.getAttribute("data-item-id");
      rowEl.querySelectorAll(".qty-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
          const current = bookingState.drinks[itemId] || 0;
          const action = btn.getAttribute("data-action");
          const next = action === "inc" ? current + 1 : Math.max(0, current - 1);

          if (next === 0) {
            delete bookingState.drinks[itemId];
          } else {
            bookingState.drinks[itemId] = next;
          }

          rowEl.querySelector(".qty-value").textContent = next;
          updateFuelSubtotal();
        });
      });
    });

    updateFuelSubtotal();
  }

  function updateFuelSubtotal() {
    const subtotalEl = document.getElementById("fuelSubtotal");
    if (!subtotalEl) return;
    subtotalEl.textContent = `₦${getDrinksTotal().toFixed(2)}`;
  }

  function getDrinksTotal() {
    let total = 0;
    Object.keys(bookingState.drinks).forEach((itemId) => {
      const qty = bookingState.drinks[itemId];
      const item = DATA.fuelBarMenu[itemId];
      if (item) total += item.price * qty;
    });
    return total;
  }

  function getDrinksPayload() {
    return Object.keys(bookingState.drinks).map((itemId) => ({
      item_id: itemId,
      qty: bookingState.drinks[itemId],
    }));
  }

  // --------------------------------------------------------------------
  // Booking modal
  // --------------------------------------------------------------------

  window.openBookingModal = function () {
    const zoneSelect = document.getElementById("bookingZone");
    const banner = document.getElementById("selectedZoneBanner");
    const bannerLabel = document.getElementById("selectedZoneLabel");

    if (bookingState.zoneId && DATA.zones[bookingState.zoneId]) {
      zoneSelect.value = bookingState.zoneId;
      banner.style.display = "flex";
      bannerLabel.textContent = `Zone selected: ${DATA.zones[bookingState.zoneId].name}`;
    } else if (zoneSelect.value) {
      banner.style.display = "flex";
      bannerLabel.textContent = `Zone selected: ${DATA.zones[zoneSelect.value].name}`;
    } else {
      banner.style.display = "none";
    }

    renderBookingDrinksList();
    recalculateCosts();
    openModal("bookingModal");
  };

  function renderBookingDrinksList() {
    const el = document.getElementById("bookingDrinksList");
    const itemIds = Object.keys(bookingState.drinks);
    if (itemIds.length === 0) {
      el.innerHTML = "";
      return;
    }
    const lines = itemIds
      .map((itemId) => {
        const item = DATA.fuelBarMenu[itemId];
        const qty = bookingState.drinks[itemId];
        return `<div>${qty} × <span>${escapeHtml(item.name)}</span></div>`;
      })
      .join("");
    el.innerHTML = `<strong>Fuel Bar items added:</strong>${lines}`;
  }

  function wireBookingFormEvents() {
    const zoneSelect = document.getElementById("bookingZone");
    const durationSelect = document.getElementById("bookingDuration");
    if (!zoneSelect || !durationSelect) return;

    zoneSelect.addEventListener("change", () => {
      bookingState.zoneId = zoneSelect.value || null;
      const banner = document.getElementById("selectedZoneBanner");
      const bannerLabel = document.getElementById("selectedZoneLabel");
      if (zoneSelect.value) {
        banner.style.display = "flex";
        bannerLabel.textContent = `Zone selected: ${DATA.zones[zoneSelect.value].name}`;
      } else {
        banner.style.display = "none";
      }
      recalculateCosts();
    });

    durationSelect.addEventListener("change", recalculateCosts);
  }

  function recalculateCosts() {
    const zoneSelect = document.getElementById("bookingZone");
    const durationSelect = document.getElementById("bookingDuration");
    if (!zoneSelect || !durationSelect) return;

    const zoneId = zoneSelect.value;
    const durationMin = parseInt(durationSelect.value, 10) || 0;
    const zone = zoneId ? DATA.zones[zoneId] : null;

    const zoneCost = zone ? (zone.price_per_game || 3000) * durationMin : 0;
    const drinksCost = getDrinksTotal();
    const total = zoneCost + drinksCost;

    document.getElementById('summaryZoneCost').textContent = `₦${zoneCost.toLocaleString()}`;
    document.getElementById('summaryDrinksCost').textContent = `₦${drinksCost.toLocaleString()}`;
    document.getElementById('summaryTotal').textContent = `₦${total.toLocaleString()}`;
}


  function wireBookingFormSubmit() {
    const form = document.getElementById("bookingForm");
    if (!form) return;

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const errorEl = document.getElementById("bookingError");
      errorEl.classList.remove("active");
      errorEl.textContent = "";

      const payload = {
        zone_id: document.getElementById("bookingZone").value,
        duration_min: parseInt(document.getElementById("bookingDuration").value, 10),
        session_date: document.getElementById("bookingDate").value,
        time_slot: document.getElementById("bookingTimeSlot").value,
        customer_name: document.getElementById("bookingName").value.trim(),
        phone: document.getElementById("bookingPhone").value.trim(),
        email: document.getElementById("bookingEmail").value.trim(),
        drinks: getDrinksPayload(),
      };

      const submitBtn = form.querySelector("button[type=submit]");
      submitBtn.disabled = true;
      submitBtn.textContent = "Submitting…";

      try {
        const res = await fetch("/book", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();

        if (!res.ok || !data.success) {
          const messages = (data.errors && data.errors.join(" ")) || "Something went wrong. Please check your details.";
          errorEl.textContent = messages;
          errorEl.classList.add("active");
          return;
        }

        window.currentBooking = data.booking;
        window.currentBankDetails = data.bank_details;
        closeModal("bookingModal");
        renderCheckout(data.booking, data.bank_details);
        openModal("checkoutModal");
        showToast("Booking received — complete your transfer to activate your pod.", "success");
      } catch (err) {
        errorEl.textContent = "Network error — please try again.";
        errorEl.classList.add("active");
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Continue to Payment";
      }
    });
  }

  // --------------------------------------------------------------------
  // Checkout modal
  // --------------------------------------------------------------------

  function renderCheckout(booking, bankDetails) {
    document.getElementById("checkoutRef").textContent = booking.ref_id;
    document.getElementById("bankName").textContent = bankDetails.bank_name;
    document.getElementById("bankAccountName").textContent = bankDetails.account_name;
    document.getElementById("bankAccountNumber").textContent = bankDetails.account_number;
    document.getElementById("bankRoutingNumber").textContent = bankDetails.routing_number;
    document.getElementById("checkoutTotal").textContent = `₦${booking.total_cost.toFixed(2)}`;
    document.getElementById("checkoutInstructions").textContent =
      `Bring a screenshot of this receipt or your transfer confirmation to the office counter to activate your pod. Reference: ${booking.ref_id}.`;
  }

  function wireCheckout() {
    const btn = document.getElementById("markPaidBtn");
    if (!btn) return;

    btn.addEventListener("click", async () => {
      if (!window.currentBooking) return;
      btn.disabled = true;
      btn.textContent = "Confirming…";

      try {
        const res = await fetch(`/book/${window.currentBooking.ref_id}/mark-paid`, {
          method: "POST",
        });
        const data = await res.json();
        if (data.success) {
          window.location.href = `/receipt/${window.currentBooking.ref_id}`;
        } else {
          showToast("Could not confirm your transfer — please try again.", "error");
        }
      } catch (err) {
        showToast("Network error — please try again.", "error");
      } finally {
        btn.disabled = false;
        btn.textContent = "I've Completed The Transfer";
      }
    });
  }

  // --------------------------------------------------------------------
  // Support / contact form
  // --------------------------------------------------------------------

  function wireSupportForm() {
    const form = document.getElementById("supportForm");
    if (!form) return;

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const errorEl = document.getElementById("supportError");
      errorEl.classList.remove("active");
      errorEl.textContent = "";

      const payload = {
        name: document.getElementById("supportName").value.trim(),
        email: document.getElementById("supportEmail").value.trim(),
        phone: document.getElementById("supportPhone").value.trim(),
        subject: document.getElementById("supportSubject").value.trim(),
        message: document.getElementById("supportMessage").value.trim(),
      };

      const submitBtn = form.querySelector("button[type=submit]");
      submitBtn.disabled = true;
      submitBtn.textContent = "Sending…";

      try {
        const res = await fetch("/support/ticket", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();

        if (!res.ok || !data.success) {
          const messages = (data.errors && data.errors.join(" ")) || "Something went wrong. Please check your details.";
          errorEl.textContent = messages;
          errorEl.classList.add("active");
          return;
        }

        form.reset();
        showToast("Message sent — our team will reply by email shortly.", "success");
      } catch (err) {
        errorEl.textContent = "Network error — please try again.";
        errorEl.classList.add("active");
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Send Message";
      }
    });
  }

  // --------------------------------------------------------------------
  // Small utilities
  // --------------------------------------------------------------------

  let toastTimeout = null;
  function showToast(message, type) {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.className = "toast show " + (type || "");
    clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => {
      toast.classList.remove("show");
    }, 4500);
  }
  window.showToast = showToast;

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }
})();
