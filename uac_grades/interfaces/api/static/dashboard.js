(() => {
  const button = document.getElementById("fetchGradesButton");
  const feedback = document.getElementById("fetchFeedback");
  const message = document.getElementById("fetchMessage");
  const gradesList = document.getElementById("fetchGradesList");

  if (!button || !feedback || !message || !gradesList) {
    return;
  }

  const resultKey = "uaGradesFetchResult";
  const cooldownKey = "uaGradesFetchCooldownUntil";
  const defaultLabel = "Actualizar notas";
  let cooldownTimer = null;
  let isRunning = false;

  function setFeedback(text, variant = "") {
    feedback.hidden = false;
    feedback.className = `fetch-feedback ${variant}`.trim();
    message.textContent = text;
    gradesList.hidden = true;
    gradesList.replaceChildren();
  }

  function renderResult(result, variant = "success") {
    setFeedback(result.message || "Notas actualizadas.", variant);

    if (!Array.isArray(result.new_grades) || result.new_grades.length === 0) {
      return;
    }

    const fragment = document.createDocumentFragment();
    result.new_grades.forEach((grade) => {
      const item = document.createElement("li");
      const course = document.createElement("strong");
      const courseCode = grade.course_code ? `${grade.course_code} - ` : "";
      course.textContent = `${courseCode}${grade.course_title || "Ramo"}`;

      const previous = grade.previous_grade
        ? ` (antes ${grade.previous_grade})`
        : "";
      item.append(
        course,
        document.createTextNode(
          `: ${grade.evaluation || "Nota"} = ${grade.grade}${previous}`
        )
      );
      fragment.append(item);
    });

    gradesList.replaceChildren(fragment);
    gradesList.hidden = false;
  }

  function cooldownSecondsLeft() {
    const cooldownUntil = Number(sessionStorage.getItem(cooldownKey) || 0);
    return Math.max(0, Math.ceil((cooldownUntil - Date.now()) / 1000));
  }

  function stopCooldown() {
    if (cooldownTimer) {
      window.clearInterval(cooldownTimer);
      cooldownTimer = null;
    }
  }

  function updateCooldownLabel() {
    const secondsLeft = cooldownSecondsLeft();
    if (secondsLeft <= 0) {
      stopCooldown();
      sessionStorage.removeItem(cooldownKey);
      if (!isRunning) {
        button.disabled = false;
        button.textContent = defaultLabel;
      }
      return;
    }

    button.disabled = true;
    button.textContent = `${defaultLabel} (${secondsLeft}s)`;
  }

  function startCooldown(seconds) {
    const parsedSeconds = Number(seconds) || 0;
    if (parsedSeconds <= 0) {
      updateCooldownLabel();
      return;
    }

    sessionStorage.setItem(
      cooldownKey,
      String(Date.now() + parsedSeconds * 1000)
    );
    updateCooldownLabel();
    stopCooldown();
    cooldownTimer = window.setInterval(updateCooldownLabel, 1000);
  }

  async function readError(response) {
    const body = await response.json().catch(() => null);
    const detail = body && body.detail;
    if (detail && typeof detail === "object") {
      return detail;
    }
    if (typeof detail === "string" && detail.trim()) {
      return { message: detail };
    }
    return { message: "No se pudo actualizar notas." };
  }

  async function refreshStatus() {
    if (isRunning) {
      return;
    }

    try {
      const response = await fetch("/api/fetch/status");
      if (!response.ok) {
        return;
      }
      const status = await response.json();
      if (status.running) {
        button.disabled = true;
        button.textContent = "Actualizando...";
        setFeedback("Ya hay una actualizacion de notas en curso.", "loading");
        window.setTimeout(refreshStatus, 3000);
        return;
      }
      if (status.cooldown_seconds > 0) {
        startCooldown(status.cooldown_seconds);
      } else if (cooldownSecondsLeft() <= 0) {
        button.disabled = false;
        button.textContent = defaultLabel;
      }
    } catch (_error) {
      return;
    }
  }

  async function fetchGrades() {
    isRunning = true;
    stopCooldown();
    button.disabled = true;
    button.textContent = "Actualizando...";
    setFeedback("Actualizando notas desde Banner...", "loading");

    try {
      const response = await fetch("/api/fetch", { method: "POST" });
      if (!response.ok) {
        const error = await readError(response);
        if (error.cooldown_seconds > 0) {
          setFeedback(error.message || "Espera antes de volver a actualizar.", "loading");
          startCooldown(error.cooldown_seconds);
        } else {
          setFeedback(error.message || "No se pudo actualizar notas.", "error");
          button.disabled = false;
          button.textContent = defaultLabel;
        }
        return;
      }

      const result = await response.json();
      renderResult(result, "success");
      startCooldown(result.cooldown_seconds || 60);
      sessionStorage.setItem(resultKey, JSON.stringify(result));
      window.setTimeout(() => window.location.reload(), 900);
    } catch (error) {
      setFeedback(error.message || "No se pudo conectar con el servidor local.", "error");
      button.disabled = false;
      button.textContent = defaultLabel;
    } finally {
      isRunning = false;
    }
  }

  const savedResult = sessionStorage.getItem(resultKey);
  if (savedResult) {
    sessionStorage.removeItem(resultKey);
    try {
      renderResult(JSON.parse(savedResult), "success");
    } catch (_error) {
      setFeedback("Notas actualizadas.", "success");
    }
  }

  const existingCooldown = cooldownSecondsLeft();
  if (existingCooldown > 0) {
    startCooldown(existingCooldown);
  }

  button.addEventListener("click", fetchGrades);
  refreshStatus();
})();
