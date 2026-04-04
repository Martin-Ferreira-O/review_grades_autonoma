(function () {
  const palette = {
    grid: "rgba(148, 163, 184, 0.18)",
    text: "#cbd5e1",
    accent: "#60a5fa",
    success: "#22c55e",
    danger: "#f97316",
  };

  function setupCanvas(canvas) {
    const ratio = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const logicalHeight = Number(canvas.getAttribute("height") || 220);
    canvas.width = rect.width * ratio;
    canvas.height = logicalHeight * ratio;
    const context = canvas.getContext("2d");
    context.scale(ratio, ratio);
    return { context, width: rect.width, height: logicalHeight };
  }

  function drawAxes(context, width, height, maxValue) {
    context.strokeStyle = palette.grid;
    context.lineWidth = 1;
    for (let index = 0; index <= 4; index += 1) {
      const y = 20 + ((height - 40) / 4) * index;
      context.beginPath();
      context.moveTo(45, y);
      context.lineTo(width - 12, y);
      context.stroke();

      const value = (maxValue - (maxValue / 4) * index).toFixed(1);
      context.fillStyle = palette.text;
      context.font = "12px Inter, Arial, sans-serif";
      context.fillText(value, 6, y + 4);
    }
  }

  function drawLineChart(canvasId, labels, values) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || values.length === 0) {
      return;
    }

    const { context, width, height } = setupCanvas(canvas);
    const validValues = values.filter(function (value) {
      return typeof value === "number";
    });
    if (validValues.length === 0) {
      return;
    }

    const maxValue = Math.max(4.0, ...validValues) + 0.4;
    drawAxes(context, width, height, maxValue);

    const chartWidth = width - 70;
    const chartHeight = height - 50;
    const stepX = values.length > 1 ? chartWidth / (values.length - 1) : chartWidth / 2;

    context.strokeStyle = palette.accent;
    context.lineWidth = 3;
    context.beginPath();

    let hasOpenSegment = false;
    values.forEach(function (value, index) {
      if (typeof value !== "number") {
        hasOpenSegment = false;
        return;
      }

      const x = 45 + stepX * index;
      const y = 20 + chartHeight - (value / maxValue) * chartHeight;
      if (!hasOpenSegment) {
        context.moveTo(x, y);
        hasOpenSegment = true;
      } else {
        context.lineTo(x, y);
      }
    });

    context.stroke();

    values.forEach(function (value, index) {
      if (typeof value !== "number") {
        return;
      }

      const x = 45 + stepX * index;
      const y = 20 + chartHeight - (value / maxValue) * chartHeight;
      context.fillStyle = palette.accent;
      context.beginPath();
      context.arc(x, y, 4, 0, Math.PI * 2);
      context.fill();
    });

    labels.forEach(function (label, index) {
      const x = 45 + stepX * index;
      context.fillStyle = palette.text;
      context.font = "11px Inter, Arial, sans-serif";
      const trimmed = label.length > 18 ? label.slice(0, 18) + "..." : label;
      context.save();
      context.translate(x - 8, height - 8);
      context.rotate(-Math.PI / 4);
      context.fillText(trimmed, 0, 0);
      context.restore();
    });
  }

  function drawHorizontalBars(canvasId, labels, values, color) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || values.length === 0) {
      return;
    }

    const { context, width, height } = setupCanvas(canvas);
    const maxValue = Math.max(...values, 4);
    const barAreaHeight = height - 20;
    const barHeight = Math.min(26, barAreaHeight / Math.max(values.length, 1) - 10);
    const spacing = 14;

    labels.forEach(function (label, index) {
      const y = 16 + index * (barHeight + spacing);
      const value = values[index];
      const barWidth = ((width - 170) * value) / maxValue;

      context.fillStyle = palette.text;
      context.font = "12px Inter, Arial, sans-serif";
      context.fillText(label.length > 26 ? label.slice(0, 26) + "..." : label, 8, y + 16);

      context.fillStyle = "rgba(148, 163, 184, 0.15)";
      context.fillRect(150, y, width - 170, barHeight);

      context.fillStyle = color;
      context.fillRect(150, y, barWidth, barHeight);

      context.fillStyle = palette.text;
      context.fillText(value.toFixed(2), width - 45, y + 16);
    });
  }

  const data = window.dashboardData;
  if (!data) {
    return;
  }

  drawLineChart("termTrendChart", data.termLabels, data.termAverages);
  drawHorizontalBars("bestCoursesChart", data.bestLabels, data.bestValues, palette.success);
  drawHorizontalBars("worstCoursesChart", data.worstLabels, data.worstValues, palette.danger);

  window.addEventListener("resize", function () {
    drawLineChart("termTrendChart", data.termLabels, data.termAverages);
    drawHorizontalBars("bestCoursesChart", data.bestLabels, data.bestValues, palette.success);
    drawHorizontalBars("worstCoursesChart", data.worstLabels, data.worstValues, palette.danger);
  });
})();
