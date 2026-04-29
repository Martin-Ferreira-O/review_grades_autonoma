(function () {
  const data = window.dashboardData;
  if (!data) {
    return;
  }

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const palette = {
    grid: "#d7e5ef",
    label: "#466579",
    text: "#082f49",
    muted: "#6b8798",
    track: "#e8f3f9",
    primary: "#0ea5e9",
    primaryDark: "#0369a1",
    success: "#16a34a",
    warning: "#d97706",
    danger: "#dc2626",
    orange: "#f97316",
  };

  function numberList(values) {
    return Array.isArray(values)
      ? values.map((value) => (typeof value === "number" && Number.isFinite(value) ? value : null))
      : [];
  }

  function labelList(values) {
    return Array.isArray(values) ? values.map((value) => String(value || "")) : [];
  }

  function getLogicalHeight(canvas) {
    if (canvas.dataset.logicalHeight) {
      return Number(canvas.dataset.logicalHeight);
    }

    const cssHeight = Number.parseFloat(getComputedStyle(canvas).getPropertyValue("--chart-height"));
    const attrHeight = Number(canvas.getAttribute("height") || 240);
    const requestedHeight = Number.isFinite(cssHeight) && cssHeight > 0 ? cssHeight : attrHeight;
    const logicalHeight = Math.max(180, Math.min(requestedHeight, 420));
    canvas.dataset.logicalHeight = String(logicalHeight);
    return logicalHeight;
  }

  function setupCanvas(canvas) {
    const ratio = window.devicePixelRatio || 1;
    const logicalHeight = getLogicalHeight(canvas);
    canvas.style.height = `${logicalHeight}px`;

    const rect = canvas.getBoundingClientRect();
    const parentRect = canvas.parentElement ? canvas.parentElement.getBoundingClientRect() : { width: 0 };
    const width = Math.max(rect.width || parentRect.width || canvas.clientWidth || 0, 280);
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(logicalHeight * ratio);
    const context = canvas.getContext("2d");
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, logicalHeight);
    return { context, width, height: logicalHeight };
  }

  function setFont(context, size, weight) {
    context.font = `${weight || 600} ${size}px "Fira Sans", Arial, sans-serif`;
  }

  function trimLabel(context, label, maxWidth) {
    if (context.measureText(label).width <= maxWidth) {
      return label;
    }

    let trimmed = label;
    while (trimmed.length > 4 && context.measureText(`${trimmed}...`).width > maxWidth) {
      trimmed = trimmed.slice(0, -1);
    }
    return `${trimmed}...`;
  }

  function drawEmpty(context, width, height, text) {
    context.fillStyle = palette.track;
    context.fillRect(0, 0, width, height);
    context.fillStyle = palette.muted;
    setFont(context, 13, 700);
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(text || "Sin datos suficientes", width / 2, height / 2);
    context.textAlign = "left";
    context.textBaseline = "alphabetic";
  }

  function drawProgressBars(canvas, labels, values, progress) {
    const { context, width, height } = setupCanvas(canvas);
    const usableLabels = labelList(labels);
    const usableValues = numberList(values);
    const rows = usableLabels
      .map((label, index) => ({ label, value: usableValues[index] }))
      .filter((row) => row.label && row.value !== null);

    if (rows.length === 0) {
      drawEmpty(context, width, height, "Sin avance evaluado");
      return;
    }

    const top = 8;
    const rowHeight = Math.max(34, (height - 16) / rows.length);
    const labelWidth = Math.min(width * 0.42, 190);
    const barX = labelWidth + 12;
    const barWidth = Math.max(width - barX - 52, 90);

    rows.forEach((row, index) => {
      const y = top + index * rowHeight;
      const barY = y + rowHeight / 2 - 5;
      const value = Math.max(0, Math.min(100, row.value));

      context.fillStyle = palette.text;
      setFont(context, 12, 700);
      context.fillText(trimLabel(context, row.label, labelWidth), 0, y + 14);

      context.fillStyle = palette.track;
      context.fillRect(barX, barY, barWidth, 10);

      context.fillStyle = value >= 70 ? palette.success : value >= 35 ? palette.primary : palette.warning;
      context.fillRect(barX, barY, (barWidth * value * progress) / 100, 10);

      context.fillStyle = palette.muted;
      setFont(context, 12, 700);
      context.fillText(`${Math.round(value)}%`, barX + barWidth + 12, barY + 10);
    });
  }

  function drawPressureBars(canvas, labels, values, texts, progress) {
    const { context, width, height } = setupCanvas(canvas);
    const usableLabels = labelList(labels);
    const usableTexts = labelList(texts);
    const usableValues = numberList(values);
    const rows = usableLabels
      .map((label, index) => ({ label, value: usableValues[index], text: usableTexts[index] || "" }))
      .filter((row) => row.label && row.value !== null);

    if (rows.length === 0) {
      drawEmpty(context, width, height, "Sin presion calculada");
      return;
    }

    const top = 8;
    const rowHeight = Math.max(34, (height - 16) / rows.length);
    const labelWidth = Math.min(width * 0.42, 190);
    const barX = labelWidth + 12;
    const barWidth = Math.max(width - barX - 54, 90);
    const scaleMax = 7.1;

    [4, 5.5].forEach((target) => {
      const x = barX + (barWidth * target) / scaleMax;
      context.strokeStyle = target === 4 ? "rgba(22, 163, 74, 0.42)" : "rgba(249, 115, 22, 0.42)";
      context.beginPath();
      context.moveTo(x, 4);
      context.lineTo(x, height - 4);
      context.stroke();
    });

    rows.forEach((row, index) => {
      const y = top + index * rowHeight;
      const barY = y + rowHeight / 2 - 5;
      const value = Math.max(0, Math.min(scaleMax, row.value));
      const color = value === 0
        ? palette.success
        : value > 5.5
          ? palette.danger
          : value > 4
            ? palette.warning
            : palette.primary;

      context.fillStyle = palette.text;
      setFont(context, 12, 700);
      context.fillText(trimLabel(context, row.label, labelWidth), 0, y + 14);

      context.fillStyle = palette.track;
      context.fillRect(barX, barY, barWidth, 10);

      context.fillStyle = color;
      context.fillRect(barX, barY, (barWidth * value * progress) / scaleMax, 10);

      context.fillStyle = palette.muted;
      setFont(context, 12, 700);
      context.fillText(row.text || value.toFixed(2), barX + barWidth + 12, barY + 10);
    });
  }

  function drawMarginBars(canvas, labels, values, texts, progress) {
    const { context, width, height } = setupCanvas(canvas);
    const usableLabels = labelList(labels);
    const usableTexts = labelList(texts);
    const usableValues = numberList(values);
    const rows = usableLabels
      .map((label, index) => ({ label, value: usableValues[index], text: usableTexts[index] || "" }))
      .filter((row) => row.label && row.value !== null);

    if (rows.length === 0) {
      drawEmpty(context, width, height, "Sin asistencia cargada");
      return;
    }

    const top = 8;
    const rowHeight = Math.max(34, (height - 16) / rows.length);
    const labelWidth = Math.min(width * 0.38, 180);
    const barX = labelWidth + 16;
    const textWidth = 44;
    const sideWidth = Math.max((width - barX - textWidth - 18) / 2, 58);
    const zeroX = barX + sideWidth;
    const maxAbs = Math.max(1, ...rows.map((row) => Math.abs(row.value)));

    context.strokeStyle = palette.grid;
    context.beginPath();
    context.moveTo(zeroX, 4);
    context.lineTo(zeroX, height - 4);
    context.stroke();

    rows.forEach((row, index) => {
      const y = top + index * rowHeight;
      const barY = y + rowHeight / 2 - 5;
      const magnitude = (Math.abs(row.value) / maxAbs) * sideWidth * progress;
      const color = row.value < 0
        ? palette.danger
        : row.value === 0
          ? palette.warning
          : row.value <= 1
            ? palette.primary
            : palette.success;

      context.fillStyle = palette.text;
      setFont(context, 12, 700);
      context.fillText(trimLabel(context, row.label, labelWidth), 0, y + 14);

      context.fillStyle = palette.track;
      context.fillRect(barX, barY, sideWidth * 2, 10);

      context.fillStyle = color;
      if (row.value < 0) {
        context.fillRect(zeroX - magnitude, barY, magnitude, 10);
      } else {
        context.fillRect(zeroX, barY, magnitude, 10);
      }

      context.fillStyle = palette.muted;
      setFont(context, 12, 700);
      context.fillText(row.text || String(row.value), zeroX + sideWidth + 12, barY + 10);
    });
  }

  function drawGradeBars(canvas, labels, values, color, progress) {
    const { context, width, height } = setupCanvas(canvas);
    const usableLabels = labelList(labels);
    const usableValues = numberList(values);
    const rows = usableLabels
      .map((label, index) => ({ label, value: usableValues[index] }))
      .filter((row) => row.label && row.value !== null);

    if (rows.length === 0) {
      drawEmpty(context, width, height, "Sin notas numericas");
      return;
    }

    const top = 8;
    const rowHeight = Math.max(34, (height - 16) / rows.length);
    const labelWidth = Math.min(width * 0.42, 185);
    const barX = labelWidth + 12;
    const barWidth = Math.max(width - barX - 52, 90);

    rows.forEach((row, index) => {
      const y = top + index * rowHeight;
      const barY = y + rowHeight / 2 - 5;
      const value = Math.max(0, Math.min(7, row.value));

      context.fillStyle = palette.text;
      setFont(context, 12, 700);
      context.fillText(trimLabel(context, row.label, labelWidth), 0, y + 14);

      context.fillStyle = palette.track;
      context.fillRect(barX, barY, barWidth, 10);

      context.fillStyle = color;
      context.fillRect(barX, barY, (barWidth * value * progress) / 7, 10);

      context.fillStyle = palette.muted;
      setFont(context, 12, 700);
      context.fillText(value.toFixed(2), barX + barWidth + 12, barY + 10);
    });
  }

  function drawLineChart(canvas, labels, values, progress) {
    const { context, width, height } = setupCanvas(canvas);
    const usableLabels = labelList(labels);
    const usableValues = numberList(values);
    const validValues = usableValues.filter((value) => value !== null);

    if (validValues.length === 0) {
      drawEmpty(context, width, height, "Sin tendencia historica");
      return;
    }

    const left = 38;
    const right = 14;
    const top = 14;
    const bottom = width < 440 ? 54 : 42;
    const chartWidth = width - left - right;
    const chartHeight = height - top - bottom;
    const minValue = 1;
    const maxValue = 7;

    [7, 5.5, 4, 1].forEach((grade) => {
      const y = top + ((maxValue - grade) / (maxValue - minValue)) * chartHeight;
      context.strokeStyle = grade === 4 ? "rgba(22, 163, 74, 0.36)" : palette.grid;
      context.beginPath();
      context.moveTo(left, y);
      context.lineTo(width - right, y);
      context.stroke();

      context.fillStyle = palette.muted;
      setFont(context, 11, 700);
      context.fillText(grade.toFixed(1), 4, y + 4);
    });

    const stepX = usableValues.length > 1 ? chartWidth / (usableValues.length - 1) : chartWidth / 2;
    const points = usableValues.map((value, index) => {
      if (value === null) {
        return null;
      }
      return {
        x: left + stepX * index,
        y: top + ((maxValue - Math.max(minValue, Math.min(maxValue, value))) / (maxValue - minValue)) * chartHeight,
      };
    });

    context.save();
    context.beginPath();
    context.rect(left, 0, chartWidth * progress, height);
    context.clip();

    context.strokeStyle = palette.primary;
    context.lineWidth = 3;
    context.beginPath();
    let open = false;
    points.forEach((point) => {
      if (!point) {
        open = false;
        return;
      }
      if (!open) {
        context.moveTo(point.x, point.y);
        open = true;
      } else {
        context.lineTo(point.x, point.y);
      }
    });
    context.stroke();

    points.forEach((point) => {
      if (!point) {
        return;
      }
      context.fillStyle = "#ffffff";
      context.beginPath();
      context.arc(point.x, point.y, 5, 0, Math.PI * 2);
      context.fill();
      context.strokeStyle = palette.primaryDark;
      context.lineWidth = 2;
      context.stroke();
    });
    context.restore();

    usableLabels.forEach((label, index) => {
      if (!label) {
        return;
      }
      const x = left + stepX * index;
      const trimmed = label.length > 18 ? `${label.slice(0, 18)}...` : label;
      context.save();
      context.translate(x - 6, height - 10);
      context.rotate(width < 520 ? -Math.PI / 4 : -Math.PI / 6);
      context.fillStyle = palette.muted;
      setFont(context, 10, 700);
      context.fillText(trimmed, 0, 0);
      context.restore();
    });
  }

  const charts = [
    {
      id: "courseProgressChart",
      draw: (canvas, progress) => drawProgressBars(canvas, data.currentLabels, data.progressValues, progress),
    },
    {
      id: "coursePressureChart",
      draw: (canvas, progress) => drawPressureBars(canvas, data.currentLabels, data.pressureValues, data.pressureTexts, progress),
    },
    {
      id: "attendanceMarginChart",
      draw: (canvas, progress) => drawMarginBars(canvas, data.attendanceLabels, data.attendanceMargins, data.attendanceMarginTexts, progress),
    },
    {
      id: "termTrendChart",
      draw: (canvas, progress) => drawLineChart(canvas, data.termLabels, data.termAverages, progress),
    },
    {
      id: "bestCoursesChart",
      draw: (canvas, progress) => drawGradeBars(canvas, data.bestLabels, data.bestValues, palette.success, progress),
    },
    {
      id: "worstCoursesChart",
      draw: (canvas, progress) => drawGradeBars(canvas, data.worstLabels, data.worstValues, palette.danger, progress),
    },
  ];

  function drawDefinition(definition, progress) {
    const canvas = document.getElementById(definition.id);
    if (!canvas) {
      return;
    }
    definition.draw(canvas, progress);
  }

  function animateDefinition(definition) {
    if (reducedMotion) {
      drawDefinition(definition, 1);
      return;
    }

    const started = performance.now();
    const duration = 780;

    function frame(now) {
      const progress = Math.min((now - started) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      drawDefinition(definition, eased);
      if (progress < 1) {
        window.requestAnimationFrame(frame);
      }
    }

    window.requestAnimationFrame(frame);
  }

  if ("IntersectionObserver" in window && !reducedMotion) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) {
            return;
          }

          const definition = charts.find((chart) => chart.id === entry.target.id);
          if (definition) {
            animateDefinition(definition);
            observer.unobserve(entry.target);
          }
        });
      },
      { rootMargin: "0px 0px -10% 0px", threshold: 0.18 }
    );

    charts.forEach((definition) => {
      const canvas = document.getElementById(definition.id);
      if (canvas) {
        observer.observe(canvas);
      }
    });
  } else {
    charts.forEach((definition) => drawDefinition(definition, 1));
  }

  let resizeTimer = null;
  window.addEventListener("resize", function () {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(function () {
      charts.forEach((definition) => drawDefinition(definition, 1));
    }, 120);
  });
})();
