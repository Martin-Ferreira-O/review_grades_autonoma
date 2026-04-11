(function () {
  function initTabs() {
    const containers = document.querySelectorAll("[data-tabs]");

    containers.forEach((container) => {
      const tabs = Array.from(container.querySelectorAll("[data-tab-target]"));
      const panels = Array.from(document.querySelectorAll("[data-tab-panel]"));
      const activeTabInputs = Array.from(document.querySelectorAll("[data-active-tab-input]"));

      if (!tabs.length || !panels.length) {
        return;
      }

      const activate = (target) => {
        tabs.forEach((tab) => {
          const isActive = tab.dataset.tabTarget === target;
          tab.classList.toggle("is-active", isActive);
          tab.setAttribute("aria-selected", String(isActive));
          tab.tabIndex = isActive ? 0 : -1;
        });

        panels.forEach((panel) => {
          const isActive = panel.dataset.tabPanel === target;
          panel.classList.toggle("is-active", isActive);
          panel.hidden = !isActive;
        });

        activeTabInputs.forEach((input) => {
          input.value = target;
        });

        container.dataset.activeTab = target;
      };

      const focusTabAtIndex = (index) => {
        const tab = tabs[index];
        if (!(tab instanceof HTMLButtonElement)) {
          return;
        }

        activate(tab.dataset.tabTarget || "course");
        tab.focus();
      };

      tabs.forEach((tab) => {
        tab.addEventListener("click", () => {
          activate(tab.dataset.tabTarget || "course");
        });

        tab.addEventListener("keydown", (event) => {
          const currentIndex = tabs.indexOf(tab);
          if (currentIndex === -1) {
            return;
          }

          if (event.key === "ArrowRight" || event.key === "ArrowDown") {
            event.preventDefault();
            focusTabAtIndex((currentIndex + 1) % tabs.length);
            return;
          }

          if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
            event.preventDefault();
            focusTabAtIndex((currentIndex - 1 + tabs.length) % tabs.length);
            return;
          }

          if (event.key === "Home") {
            event.preventDefault();
            focusTabAtIndex(0);
            return;
          }

          if (event.key === "End") {
            event.preventDefault();
            focusTabAtIndex(tabs.length - 1);
          }
        });
      });

      activate(container.dataset.activeTab || "course");
    });
  }

  function setFeedback(node, message, state) {
    if (!node) {
      return;
    }

    node.textContent = message;
    node.classList.remove("is-success", "is-error", "is-pending");
    if (state) {
      node.classList.add(state);
    }
  }

  function initSyncForm() {
    const form = document.querySelector("[data-sync-form]");
    if (!(form instanceof HTMLFormElement) || typeof window.fetch !== "function") {
      return;
    }

    const feedback = form.querySelector("[data-sync-feedback]");
    const submitButton = form.querySelector("[data-sync-submit]");
    const displayNameNode = document.getElementById("sync-display-name");
    const linkStateNode = document.getElementById("sync-link-state");
    const lastSyncedNode = document.getElementById("sync-last-synced");
    const claimCodeInput = form.elements.namedItem("claim_code");
    const participantInput = form.elements.namedItem("participant_name");

    form.addEventListener("submit", async (event) => {
      event.preventDefault();

      const payload = {
        participant_name: participantInput instanceof HTMLInputElement ? participantInput.value.trim() : "",
      };

      if (claimCodeInput instanceof HTMLInputElement && !claimCodeInput.disabled) {
        payload.claim_code = claimCodeInput.value.trim();
      }

      if (!payload.participant_name) {
        setFeedback(feedback, "Debes indicar un nombre visible antes de sincronizar.", "is-error");
        return;
      }

      if (submitButton instanceof HTMLButtonElement) {
        submitButton.disabled = true;
      }
      setFeedback(feedback, "Sincronizando historial local con el servicio remoto...", "is-pending");

      try {
        const response = await window.fetch(form.action, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });

        let body = {};
        try {
          body = await response.json();
        } catch (_error) {
          body = {};
        }

        if (!response.ok) {
          const detail = typeof body.detail === "string" ? body.detail : "No se pudo completar la sincronizacion.";
          setFeedback(feedback, detail, "is-error");
          return;
        }

        const participantName = typeof body.participant_name === "string" ? body.participant_name : payload.participant_name;
        const syncedAt = typeof body.synced_at === "string" ? body.synced_at : "Sin timestamp disponible";
        const state = body.state === "linked" ? "Vinculado" : "Actualizado";

        setFeedback(
          feedback,
          `Sync completo: ${body.synced_courses || 0} ramos y ${body.synced_assessments || 0} evaluaciones procesadas.`,
          "is-success"
        );

        if (displayNameNode) {
          displayNameNode.textContent = participantName;
        }
        if (linkStateNode) {
          linkStateNode.textContent = state;
        }
        if (lastSyncedNode) {
          lastSyncedNode.textContent = syncedAt;
        }
        if (participantInput instanceof HTMLInputElement) {
          participantInput.value = participantName;
          participantInput.readOnly = true;
        }
        if (claimCodeInput instanceof HTMLInputElement) {
          claimCodeInput.value = "";
          claimCodeInput.disabled = true;
        }
      } catch (_error) {
        setFeedback(feedback, "No se pudo conectar con el servicio de comparacion.", "is-error");
      } finally {
        if (submitButton instanceof HTMLButtonElement) {
          submitButton.disabled = false;
        }
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initTabs();
    initSyncForm();
  });
})();
