const LABEL_LINE_HEIGHT = 12;
const LABEL_BLOCK_GAP = 14;
const LABEL_PIECE_GAP = 8;
const LABEL_STACK_GAP = 14;
const LABEL_WIDTH = 178;
const FUTURE_PADDING_MONTHS = 10;
const FUTURE_LABEL_MONTHS = 4;

class CareerTimeline {
  constructor(container, data, activeFilters) {
    this.container = container;
    this.data = data;
    this.activeFilters = activeFilters;
    this.width = Math.max(1280, (this.yearSpan() + 1) * 170);
    this.height = 820;
    this.margin = { top: 26, right: 42, bottom: 46, left: 110 };
    this.baseline = 360;
    this.container.style.width = `${this.width}px`;
    this.svg = window.d3
      .select(container)
      .append("svg")
      .attr("width", this.width)
      .attr("height", this.height)
      .attr("viewBox", `0 0 ${this.width} ${this.height}`);
    this.root = this.svg.append("g").attr("class", "career-root");
    this.zoom = window.d3
      .zoom()
      .scaleExtent([1, 7])
      .translateExtent([
        [0, 0],
        [this.width, this.height],
      ])
      .on("zoom", (event) => {
        this.root.attr("transform", event.transform);
      });
    this.svg.call(this.zoom);
    this.container.classList.add("loaded");
  }

  yearSpan() {
    const startYear = Number((this.data.range.start || "").slice(0, 4));
    const endYear = Number((this.data.range.end || "").slice(0, 4));
    if (!startYear || !endYear) {
      return 8;
    }
    return Math.max(endYear - startYear, 6);
  }

  render() {
    this.root.selectAll("*").remove();

    const items = this.data.items.filter((item) => this.activeFilters.has(item.type));
    const markers = this.data.markers.filter((marker) => this.activeFilters.has(marker.type));
    const x = window.d3
      .scaleTime()
      .domain([
        offsetDate(parseCareerDate(this.data.range.start), -4),
        offsetDate(parseCareerDate(this.data.range.end), FUTURE_PADDING_MONTHS),
      ])
      .range([this.margin.left, this.width - this.margin.right]);

    this.drawAxis(x);
    this.drawLaneLabels(x);
    this.drawBlocks(x, items);
    this.drawMarkers(x, markers);
  }

  resetZoom() {
    this.svg.transition().duration(250).call(this.zoom.transform, window.d3.zoomIdentity);
  }

  drawAxis(x) {
    this.root
      .append("line")
      .attr("class", "career-axis-line")
      .attr("x1", this.margin.left)
      .attr("x2", this.width - this.margin.right)
      .attr("y1", this.baseline)
      .attr("y2", this.baseline);

    const ticks = x.ticks(window.d3.timeYear.every(1));
    const tickGroup = this.root.append("g").attr("class", "career-axis");
    tickGroup
      .selectAll("line")
      .data(ticks)
      .join("line")
      .attr("x1", (tick) => x(tick))
      .attr("x2", (tick) => x(tick))
      .attr("y1", this.baseline - 310)
      .attr("y2", this.baseline + 380);
    tickGroup
      .selectAll("text")
      .data(ticks)
      .join("text")
      .attr("x", (tick) => x(tick))
      .attr("y", this.baseline + 30)
      .text((tick) => tick.getFullYear());
  }

  drawLaneLabels(x) {
    const labels = [
      { text: "Certifications", y: 42 },
      { text: "Experience", y: this.baseline - 92 },
      { text: "Education", y: this.baseline + 88 },
      { text: "Honors", y: this.baseline + 210 },
      { text: "Research Stays", y: this.baseline + 344 },
    ];
    const futureLabelX = x(
      offsetDate(parseCareerDate(this.data.range.end), FUTURE_LABEL_MONTHS),
    );
    const positionedLabels = labels.flatMap((label) => [
      { ...label, x: 20, anchor: "start" },
      { ...label, x: futureLabelX, anchor: "start" },
    ]);
    this.root
      .append("g")
      .attr("class", "career-lane-labels")
      .selectAll("text")
      .data(positionedLabels)
      .join("text")
      .attr("x", (label) => label.x)
      .attr("y", (label) => label.y)
      .attr("text-anchor", (label) => label.anchor)
      .text((label) => label.text);
  }

  drawBlocks(x, items) {
    const education = assignLanes(items.filter((item) => item.type === "education"));
    const experience = assignLanes(items.filter((item) => item.type === "experience"));
    const stays = assignLanes(items.filter((item) => item.type === "stay"));
    const blockData = [
      ...experience.map((item) => ({ ...item, y: this.baseline - 46 - item.lane * 92 })),
      ...education.map((item) => ({ ...item, y: this.baseline + 44 + item.lane * 38 })),
      ...stays.map((item) => ({ ...item, y: this.baseline + 300 + item.lane * 72 })),
    ];
    const blocks = this.root
      .append("g")
      .attr("class", "career-block-layer")
      .selectAll("g")
      .data(blockData)
      .join("g")
      .attr("class", (item) => `career-block ${item.type}${item.is_current ? " current" : ""}`)
      .attr("transform", (item) => `translate(${x(parseCareerDate(item.start))},${item.y})`);

    blocks
      .append("rect")
      .attr("width", (item) => blockWidth(item, x))
      .attr("height", 26)
      .attr("rx", 9);

    blocks
      .filter((item) => item.grants.length > 0)
      .append("line")
      .attr("class", "career-grant-edge")
      .attr("x1", 0)
      .attr("x2", (item) => blockWidth(item, x))
      .attr("y1", (item) => edgeY(item))
      .attr("y2", (item) => edgeY(item));

    blocks
      .append("text")
      .attr("class", "career-block-inner-label")
      .attr("x", 8)
      .attr("y", 17)
      .text((item) => innerBlockLabel(item, blockWidth(item, x)));

    const labelStacks = placeStacks(
      blockData.flatMap((item) => itemLabelStacks(item, x)),
    );
    const stackGroups = this.root
      .append("g")
      .attr("class", "career-label-stack-layer")
      .selectAll("g")
      .data(labelStacks)
      .join("g")
      .attr("class", "career-label-stack");

    stackGroups.each(function drawStack(stack) {
      const stackGroup = window.d3.select(this);
      stack.pieces.forEach((piece) => {
        const pieceGroup = stackGroup
          .append("g")
          .attr("class", `career-${piece.kind}-label ${stack.type}`)
          .attr("transform", `translate(${stack.x},${piece.y})`);
        appendWrappedText(pieceGroup, piece.lines, 0, 0);
      });
    });

    blocks.append("title").text((item) => blockTitle(item));
  }

  drawMarkers(x, markers) {
    const certifications = assignMarkerLanes(
      markers.filter((marker) => marker.type === "certification"),
      x,
      "top",
      this.baseline,
    );
    const honors = assignMarkerLanes(
      markers.filter((marker) => marker.type === "honor"),
      x,
      "bottom",
      this.baseline,
    );
    const positioned = [...certifications, ...honors];
    const markerGroups = this.root
      .append("g")
      .attr("class", "career-marker-layer")
      .selectAll("g")
      .data(positioned)
      .join("g")
      .attr("class", (marker) => `career-marker ${marker.type}`)
      .attr("transform", (marker) => `translate(${x(parseCareerDate(marker.date))},0)`);

    markerGroups
      .append("line")
      .attr("x1", 0)
      .attr("x2", 0)
      .attr("y1", this.baseline)
      .attr("y2", (marker) =>
        marker.type === "honor" ? marker.yAnchor - 10 : marker.yAnchor + 10,
      );

    markerGroups
      .append("path")
      .attr("d", (marker) =>
        marker.type === "honor"
          ? "M0,-7 L7,0 L0,7 L-7,0Z"
          : "M-7,0 A7,7 0 1,0 7,0 A7,7 0 1,0 -7,0 M-3,0 H3",
      )
      .attr("transform", (marker) => `translate(0,${marker.yAnchor})`);

    markerGroups.each(function drawMarkerLabel(marker) {
      const labelGroup = window.d3
        .select(this)
        .append("g")
        .attr("class", "career-marker-label")
        .attr("transform", `translate(10,${marker.yAnchor - 5})`);
      appendWrappedText(labelGroup, markerLabelLines(marker), 0, 0);
    });

    markerGroups.append("title").text((marker) => markerTitle(marker));
  }

  scrollToLatest() {
    const scroller = this.container.closest(".career-timeline-scroll");
    if (scroller) {
      scroller.scrollLeft = scroller.scrollWidth;
    }
  }
}

function parseCareerDate(value) {
  const text = String(value || "");
  return new Date(`${text.slice(0, 10)}T00:00:00`);
}

function offsetDate(value, months) {
  const copy = new Date(value.getTime());
  copy.setMonth(copy.getMonth() + months);
  return copy;
}

function assignLanes(items) {
  const lanes = [];
  return [...items]
    .sort((a, b) => parseCareerDate(a.start) - parseCareerDate(b.start))
    .map((item) => {
      const start = parseCareerDate(item.start).getTime();
      const end = parseCareerDate(item.end).getTime();
      const lane = lanes.findIndex((laneEnd) => start >= laneEnd);
      if (lane === -1) {
        lanes.push(end);
        return { ...item, lane: lanes.length - 1 };
      }
      lanes[lane] = end;
      return { ...item, lane };
    });
}

function assignMarkerLanes(markers, x, side, baseline) {
  const lanes = [];
  const baseY = side === "top" ? 34 : baseline + 216;
  const laneStep = side === "top" ? 70 : 66;
  return [...markers]
    .sort((a, b) => parseCareerDate(a.date) - parseCareerDate(b.date))
    .map((marker) => {
      const xPosition = x(parseCareerDate(marker.date));
      const labelWidth = 190;
      const lane = lanes.findIndex((laneEnd) => xPosition >= laneEnd + 24);
      if (lane === -1) {
        lanes.push(xPosition + labelWidth);
        return { ...marker, yAnchor: baseY + lanes.length * laneStep - laneStep };
      }
      lanes[lane] = xPosition + labelWidth;
      return { ...marker, yAnchor: baseY + lane * laneStep };
    });
}

function blockWidth(item, x) {
  return Math.max(x(parseCareerDate(item.end)) - x(parseCareerDate(item.start)), 14);
}

function textFits(value, width) {
  return String(value || "").length * 6.3 <= width;
}

function innerBlockLabel(item, width) {
  const availableWidth = width - 16;
  const label = item.subtitle ? `${item.title} · ${item.subtitle}` : item.title;
  if (availableWidth < 44) {
    return "";
  }
  if (textFits(label, availableWidth)) {
    return label;
  }
  return truncateToWidth(item.title, availableWidth);
}

function truncateToWidth(value, width) {
  const text = String(value || "");
  const maxLength = Math.max(Math.floor(width / 6.3) - 3, 0);
  if (text.length <= maxLength + 3) {
    return text;
  }
  return `${text.slice(0, maxLength)}...`;
}

function needsExternalBlockLabel(item, x) {
  const label = item.subtitle ? `${item.title} · ${item.subtitle}` : item.title;
  return !textFits(label, blockWidth(item, x) - 16);
}

function edgeY(item) {
  const bottomEdge = item.type === "education" || item.type === "stay";
  return bottomEdge ? 29 : -3;
}

function itemLabelStacks(item, x) {
  const blockLines = externalBlockLabelLines(item, x);
  const grantLines = grantLabelLines(item);
  const stacks = [];

  if (item.type === "experience") {
    const pieces = [
      ...(grantLines.length ? [{ kind: "grant", lines: grantLines }] : []),
      ...(blockLines.length ? [{ kind: "block", lines: blockLines }] : []),
    ];
    const stack = buildLabelStack(item, x, "above", pieces);
    return stack ? [stack] : [];
  }

  if (item.type === "stay") {
    const blockStack = buildLabelStack(
      item,
      x,
      "above",
      blockLines.length ? [{ kind: "block", lines: blockLines }] : [],
    );
    const grantStack = buildLabelStack(
      item,
      x,
      "below",
      grantLines.length ? [{ kind: "grant", lines: grantLines }] : [],
    );
    if (blockStack) {
      stacks.push(blockStack);
    }
    if (grantStack) {
      stacks.push(grantStack);
    }
    return stacks;
  }

  const pieces = [
    ...(blockLines.length ? [{ kind: "block", lines: blockLines }] : []),
    ...(grantLines.length ? [{ kind: "grant", lines: grantLines }] : []),
  ];
  const stack = buildLabelStack(item, x, "below", pieces);
  return stack ? [stack] : [];
}

function externalBlockLabelLines(item, x) {
  if (!needsExternalBlockLabel(item, x)) {
    return [];
  }
  return blockLabelLines(item, x);
}

function buildLabelStack(item, x, side, pieces) {
  if (!pieces.length) {
    return null;
  }

  const stack = {
    band: `${side}-${item.type}-${item.lane}`,
    direction: side === "above" ? -1 : 1,
    type: item.type,
    x: x(parseCareerDate(item.start)) + 8,
    width: LABEL_WIDTH,
    pieces: [],
  };
  if (side === "above") {
    let cursor = item.y - LABEL_BLOCK_GAP;
    [...pieces].reverse().forEach((piece) => {
      const y = cursor - (piece.lines.length - 1) * LABEL_LINE_HEIGHT;
      stack.pieces.push({ ...piece, y });
      cursor = y - LABEL_PIECE_GAP;
    });
    stack.pieces.reverse();
  } else {
    let cursor = item.y + 26 + LABEL_BLOCK_GAP;
    pieces.forEach((piece) => {
      stack.pieces.push({ ...piece, y: cursor });
      cursor += piece.lines.length * LABEL_LINE_HEIGHT + LABEL_PIECE_GAP;
    });
  }

  const firstBaseline = Math.min(...stack.pieces.map((piece) => piece.y));
  const lastBaseline = Math.max(
    ...stack.pieces.map(
      (piece) => piece.y + (piece.lines.length - 1) * LABEL_LINE_HEIGHT,
    ),
  );
  stack.height = lastBaseline - firstBaseline + LABEL_LINE_HEIGHT;
  return stack;
}

function placeStacks(stacks) {
  const laneEndsByBand = new Map();
  return [...stacks]
    .sort((a, b) => a.band.localeCompare(b.band) || a.x - b.x)
    .map((stack) => {
      const laneEnds = laneEndsByBand.get(stack.band) || [];
      const lane = laneEnds.findIndex((laneEnd) => stack.x >= laneEnd + 24);
      const laneIndex = lane === -1 ? laneEnds.length : lane;
      laneEnds[laneIndex] = stack.x + stack.width;
      laneEndsByBand.set(stack.band, laneEnds);
      const offset = laneIndex * stack.direction * (stack.height + LABEL_STACK_GAP);
      return {
        ...stack,
        pieces: stack.pieces.map((piece) => ({ ...piece, y: piece.y + offset })),
      };
    });
}

function wrapLabel(value, maxChars, maxLines) {
  const words = String(value || "").split(/\s+/).filter(Boolean);
  const lines = [];
  let line = "";
  words.forEach((word) => {
    const next = line ? `${line} ${word}` : word;
    if (next.length <= maxChars) {
      line = next;
      return;
    }
    if (line) {
      lines.push(line);
    }
    line = word;
  });
  if (line) {
    lines.push(line);
  }
  if (lines.length <= maxLines) {
    return lines;
  }
  const visible = lines.slice(0, maxLines);
  visible[maxLines - 1] = truncateLine(visible[maxLines - 1], maxChars);
  return visible;
}

function blockLabelLines(item, x) {
  if (!needsExternalBlockLabel(item, x) && item.subtitle) {
    return wrapLabel(item.subtitle, 30, 2);
  }
  return wrapDetails(item.title, item.subtitle, 30, 4);
}

function grantLabelLines(item) {
  return item.grants.flatMap((grant) => wrapDetails(grant.title, grant.subtitle, 29, 4));
}

function markerLabelLines(marker) {
  return wrapDetails(marker.title, marker.subtitle, 28, 4);
}

function wrapDetails(title, subtitle, maxChars, maxLines) {
  const lines = wrapLabel(title, maxChars, maxLines);
  const remaining = maxLines - lines.length;
  if (subtitle && remaining > 0) {
    lines.push(...wrapLabel(subtitle, maxChars, remaining));
  }
  return lines;
}

function truncateLine(value, maxChars) {
  const text = String(value || "");
  if (text.length <= maxChars - 3) {
    return `${text}...`;
  }
  return `${text.slice(0, maxChars - 3)}...`;
}

function appendWrappedText(group, lines, x, y) {
  const text = group.append("text").attr("x", x).attr("y", y);
  lines.forEach((line, index) => {
    text
      .append("tspan")
      .attr("x", x)
      .attr("dy", index === 0 ? 0 : 12)
      .text(line);
  });
  return text;
}

function blockTitle(item) {
  const lines = [`${item.title}`, `${item.date_label}`];
  if (item.subtitle) {
    lines.push(item.subtitle);
  }
  if (item.grants.length) {
    lines.push(`Grants: ${item.grants.map((grant) => grant.title).join(", ")}`);
  }
  if (item.honors.length) {
    lines.push(`Honors: ${item.honors.map((honor) => honor.title).join(", ")}`);
  }
  return lines.join("\n");
}

function markerTitle(marker) {
  return [marker.title, marker.date_label, marker.subtitle].filter(Boolean).join("\n");
}

(() => {
  const container = document.querySelector("[data-career-timeline]");
  const dataElement = document.getElementById("career-timeline-data");

  if (!container || !dataElement || !window.d3) {
    return;
  }

  const data = JSON.parse(dataElement.textContent);
  const state = new Set(data.filters.map((filter) => filter.id));
  const resetButton = document.querySelector("[data-career-reset]");
  const filterButtons = document.querySelectorAll("[data-career-filter]");
  const timeline = new CareerTimeline(container, data, state);

  filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const filter = button.dataset.careerFilter;
      if (state.has(filter)) {
        state.delete(filter);
        button.classList.remove("active");
        button.setAttribute("aria-pressed", "false");
      } else {
        state.add(filter);
        button.classList.add("active");
        button.setAttribute("aria-pressed", "true");
      }
      timeline.render();
    });
  });

  resetButton?.addEventListener("click", () => timeline.resetZoom());
  timeline.render();
  window.requestAnimationFrame(() => timeline.scrollToLatest());
})();
