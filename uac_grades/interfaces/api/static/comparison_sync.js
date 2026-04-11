(function () {
  const form = document.querySelector("[data-sync-form]");
  const feedback = document.querySelector("[data-sync-feedback]");
  const submitButton = document.querySelector("[data-sync-submit]");

  if (!(form instanceof HTMLFormElement) || !(feedback instanceof HTMLElement)) {
    return;
  }

  const displayName = document.getElementById("sync-display-name");
  const linkState = document.getElementById("sync-link-state");
  const lastSynced = document.getElementById("sync-last-synced");
  const nameInput = form.elements.namedItem("participant_name");
  const claimCodeInput = form.elements.namedItem("claim_code");

  const setFeedback = (message, tone) => {
    feedback.textContent = message;
    feedback.classList.remove("is-success", "is-error");

    if (tone) {
      feedback.classList.add(tone);
    }
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!(nameInput instanceof HTMLInputElement)) {
      form.submit();
      return;
    }

    const payload = new URLSearchParams();
    payload.set("participant_name", nameInput.value);

    if (claimCodeInput instanceof HTMLInputElement && !claimCodeInput.disabled) {
      payload.set("claim_code", claimCodeInput.value);
    }

    if (submitButton instanceof HTMLButtonElement) {
      submitButton.disabled = true;
    }

    setFeedback("Sincronizando historial local...", null);

    try {
      const response = await fetch(form.action, {
        method: form.method,
        headers: {
          "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        },
        body: payload.toString(),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "No se pudo sincronizar");
      }

      if (displayName instanceof HTMLElement) {
        displayName.textContent = data.participant_name || nameInput.value || "Sin registrar";
      }

      if (linkState instanceof HTMLElement) {
        linkState.textContent = "Vinculado";
      }

      if (lastSynced instanceof HTMLElement) {
        lastSynced.textContent = data.synced_at || "Sin fecha informada";
      }

      if (claimCodeInput instanceof HTMLInputElement) {
        claimCodeInput.value = "";
        claimCodeInput.disabled = true;
      }

      nameInput.readOnly = true;
      setFeedback("Sincronizacion completada. Ya puedes abrir el tablero remoto.", "is-success");
    } catch (error) {
      const message = error instanceof Error ? error.message : "No se pudo sincronizar";
      setFeedback(message, "is-error");
    } finally {
      if (submitButton instanceof HTMLButtonElement) {
        submitButton.disabled = false;
      }
    }
  });
})();
