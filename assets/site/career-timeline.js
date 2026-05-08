const CAREER_SELECTORS = {
  container: "[data-career-timeline]",
  data: "career-timeline-data",
  filter: "[data-career-filter]",
  loading: ".map-loading",
  reset: "[data-career-reset]",
  scroller: ".career-timeline-scroll",
};

const CAREER_MESSAGES = {
  dataUnavailable: "Career timeline data unavailable",
  dependencyUnavailable: "Career timeline library unavailable",
};

// Layout constants keep the SVG timeline stable while making visual tuning explicit.
const TIMELINE_MIN_WIDTH = 1280;
const TIMELINE_WIDTH_PER_YEAR = 170;
const TIMELINE_HEIGHT = 820;
const TIMELINE_MARGIN = { top: 26, right: 42, bottom: 46, left: 110 };
const TIMELINE_BASELINE = 360;
const TIMELINE_FALLBACK_YEAR_SPAN = 8;
const TIMELINE_MIN_YEAR_SPAN = 6;
const TIMELINE_RESET_DURATION = 250;
const TIMELINE_ZOOM_EXTENT = [1, 7];
const COMPACT_VIEWPORT_QUERY = "(max-width: 760px)";
const COMPACT_TIMELINE_MIN_WIDTH = 320;
const AXIS_TOP_OFFSET = 310;
const AXIS_BOTTOM_OFFSET = 380;
const AXIS_YEAR_LABEL_OFFSET = 30;
const PAST_PADDING_MONTHS = 4;
const FUTURE_PADDING_MONTHS = 10;
const FUTURE_LABEL_MONTHS = 4;
const FUTURE_LABEL_X_FALLBACK = 20;
const BLOCK_HEIGHT = 26;
const BLOCK_RADIUS = 9;
const BLOCK_MIN_WIDTH = 14;
const BLOCK_INNER_LABEL_X = 8;
const BLOCK_INNER_LABEL_Y = 17;
const BLOCK_EDGE_TOP_Y = -3;
const BLOCK_EDGE_BOTTOM_Y = 29;
const BLOCK_LABEL_SIDE_PADDING = 16;
const BLOCK_LABEL_MIN_WIDTH = 44;
const EXPERIENCE_LANE_OFFSET = -46;
const EXPERIENCE_LANE_STEP = 92;
const EDUCATION_LANE_OFFSET = 44;
const EDUCATION_LANE_STEP = 38;
const STAY_LANE_OFFSET = 300;
const STAY_LANE_STEP = 72;
const MARKER_LABEL_X = 10;
const MARKER_LABEL_Y_OFFSET = -5;
const MARKER_LINE_GAP = 10;
const MARKER_TOP_BASE_Y = 34;
const MARKER_BOTTOM_BASELINE_OFFSET = 216;
const MARKER_TOP_LANE_STEP = 70;
const MARKER_BOTTOM_LANE_STEP = 66;
const MARKER_LABEL_WIDTH = 190;
const STACK_COLLISION_GAP = 24;
const APPROX_CHAR_WIDTH = 6.3;
const ELLIPSIS_LENGTH = 3;
const DATE_ISO_LENGTH = 10;
const LANE_LABELS = [
  { text: "Certifications", y: 42 },
  { text: "Experience", baselineOffset: -92 },
  { text: "Education", baselineOffset: 88 },
  { text: "Honors", baselineOffset: 210 },
  { text: "Research Stays", baselineOffset: 344 },
];
const LABEL_LINE_HEIGHT = 12;
const LABEL_BLOCK_GAP = 14;
const LABEL_PIECE_GAP = 8;
const LABEL_STACK_GAP = 14;
const LABEL_WIDTH = 178;
const LABEL_MAX_CHARS = {
  block: 30,
  grant: 29,
  marker: 28,
};
const LABEL_MAX_LINES = {
  block: 4,
  subtitle: 2,
};

class CareerTimeline {
  constructor(container, data, activeFilters) {
    this.container = container;
    this.data = data;
    this.activeFilters = activeFilters;
    this.width = Math.max(
      TIMELINE_MIN_WIDTH,
      (this.yearSpan() + 1) * TIMELINE_WIDTH_PER_YEAR,
    );
    this.height = TIMELINE_HEIGHT;
    this.margin = TIMELINE_MARGIN;
    this.baseline = TIMELINE_BASELINE;
    this.displayWidth = compactTimelineDisplayWidth(this.width, this.container);
    this.displayHeight = Math.round(this.height * (this.displayWidth / this.width));
    this.container.style.width = `${this.displayWidth}px`;
    this.container.style.setProperty("--timeline-display-height", `${this.displayHeight}px`);
    this.svg = window.d3
      .select(container)
      .append("svg")
      .attr("width", this.displayWidth)
      .attr("height", this.displayHeight)
      .attr("viewBox", `0 0 ${this.width} ${this.height}`);
    this.root = this.svg.append("g").attr("class", "career-root");
    this.zoom = window.d3
      .zoom()
      .filter(shouldHandleTimelineZoom)
      .scaleExtent(TIMELINE_ZOOM_EXTENT)
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

  updateDisplaySize() {
    this.displayWidth = compactTimelineDisplayWidth(this.width, this.container);
    this.displayHeight = Math.round(this.height * (this.displayWidth / this.width));
    this.container.style.width = `${this.displayWidth}px`;
    this.container.style.setProperty("--timeline-display-height", `${this.displayHeight}px`);
    this.svg.attr("width", this.displayWidth).attr("height", this.displayHeight);
  }

  yearSpan() {
    const startYear = Number((this.data.range?.start || "").slice(0, 4));
    const endYear = Number((this.data.range?.end || "").slice(0, 4));
    if (!startYear || !endYear) {
      return TIMELINE_FALLBACK_YEAR_SPAN;
    }
    return Math.max(endYear - startYear, TIMELINE_MIN_YEAR_SPAN);
  }

  render() {
    this.root.selectAll("*").remove();

    const items = (this.data.items || []).filter((item) => this.activeFilters.has(item.type));
    const markers = (this.data.markers || []).filter((marker) => this.activeFilters.has(marker.type));
    const x = window.d3
      .scaleTime()
      .domain([
        offsetDate(parseCareerDate(this.data.range.start), -PAST_PADDING_MONTHS),
        offsetDate(parseCareerDate(this.data.range.end), FUTURE_PADDING_MONTHS),
      ])
      .range([this.margin.left, this.width - this.margin.right]);

    this.drawAxis(x);
    this.drawLaneLabels(x);
    this.drawBlocks(x, items);
    this.drawMarkers(x, markers);
  }

  resetZoom() {
    this.svg
      .transition()
      .duration(TIMELINE_RESET_DURATION)
      .call(this.zoom.transform, window.d3.zoomIdentity);
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
      .attr("y1", this.baseline - AXIS_TOP_OFFSET)
      .attr("y2", this.baseline + AXIS_BOTTOM_OFFSET);
    tickGroup
      .selectAll("text")
      .data(ticks)
      .join("text")
      .attr("x", (tick) => x(tick))
      .attr("y", this.baseline + AXIS_YEAR_LABEL_OFFSET)
      .text((tick) => tick.getFullYear());
  }

  drawLaneLabels(x) {
    const labels = LANE_LABELS.map((label) => ({
      ...label,
      y: label.y ?? this.baseline + label.baselineOffset,
    }));
    const futureLabelX = x(
      offsetDate(parseCareerDate(this.data.range.end), FUTURE_LABEL_MONTHS),
    );
    const positionedLabels = labels.flatMap((label) => [
      { ...label, x: FUTURE_LABEL_X_FALLBACK, anchor: "start" },
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
      ...experience.map((item) => ({
        ...item,
        y: this.baseline + EXPERIENCE_LANE_OFFSET - item.lane * EXPERIENCE_LANE_STEP,
      })),
      ...education.map((item) => ({
        ...item,
        y: this.baseline + EDUCATION_LANE_OFFSET + item.lane * EDUCATION_LANE_STEP,
      })),
      ...stays.map((item) => ({
        ...item,
        y: this.baseline + STAY_LANE_OFFSET + item.lane * STAY_LANE_STEP,
      })),
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
      .attr("height", BLOCK_HEIGHT)
      .attr("rx", BLOCK_RADIUS);

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
      .attr("x", BLOCK_INNER_LABEL_X)
      .attr("y", BLOCK_INNER_LABEL_Y)
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
        marker.type === "honor"
          ? marker.yAnchor - MARKER_LINE_GAP
          : marker.yAnchor + MARKER_LINE_GAP,
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
        .attr(
          "transform",
          `translate(${MARKER_LABEL_X},${marker.yAnchor + MARKER_LABEL_Y_OFFSET})`,
        );
      appendWrappedText(labelGroup, markerLabelLines(marker), 0, 0);
    });

    markerGroups.append("title").text((marker) => markerTitle(marker));
  }

  scrollToLatest() {
    const scroller = this.container.closest(CAREER_SELECTORS.scroller);
    if (scroller) {
      if (isCompactViewport()) {
        scroller.scrollTo({ left: 0, behavior: "auto" });
        return;
      }
      scroller.scrollTo({
        left: Math.max(scroller.scrollWidth - scroller.clientWidth, 0),
        behavior: "auto",
      });
    }
  }
}

function parseCareerDate(value) {
  const text = String(value || "");
  return new Date(`${text.slice(0, DATE_ISO_LENGTH)}T00:00:00`);
}

function compactTimelineDisplayWidth(width, container) {
  if (!isCompactViewport()) {
    return width;
  }
  const scroller = container.closest(CAREER_SELECTORS.scroller);
  const viewportWidth = scroller?.clientWidth || window.innerWidth || COMPACT_TIMELINE_MIN_WIDTH;
  return Math.round(Math.min(width, Math.max(viewportWidth, COMPACT_TIMELINE_MIN_WIDTH)));
}

function isCompactViewport() {
  return window.matchMedia?.(COMPACT_VIEWPORT_QUERY).matches ?? false;
}

function shouldHandleTimelineZoom(event) {
  if (isCompactViewport() && String(event.type || "").startsWith("touch")) {
    return false;
  }
  return (!event.ctrlKey || event.type === "wheel") && !event.button;
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
  const baseY =
    side === "top" ? MARKER_TOP_BASE_Y : baseline + MARKER_BOTTOM_BASELINE_OFFSET;
  const laneStep = side === "top" ? MARKER_TOP_LANE_STEP : MARKER_BOTTOM_LANE_STEP;
  return [...markers]
    .sort((a, b) => parseCareerDate(a.date) - parseCareerDate(b.date))
    .map((marker) => {
      const xPosition = x(parseCareerDate(marker.date));
      const lane = lanes.findIndex((laneEnd) => xPosition >= laneEnd + STACK_COLLISION_GAP);
      if (lane === -1) {
        lanes.push(xPosition + MARKER_LABEL_WIDTH);
        return { ...marker, yAnchor: baseY + lanes.length * laneStep - laneStep };
      }
      lanes[lane] = xPosition + MARKER_LABEL_WIDTH;
      return { ...marker, yAnchor: baseY + lane * laneStep };
    });
}

function blockWidth(item, x) {
  return Math.max(x(parseCareerDate(item.end)) - x(parseCareerDate(item.start)), BLOCK_MIN_WIDTH);
}

function textFits(value, width) {
  return String(value || "").length * APPROX_CHAR_WIDTH <= width;
}

function innerBlockLabel(item, width) {
  const availableWidth = width - BLOCK_LABEL_SIDE_PADDING;
  const label = item.subtitle ? `${item.title} · ${item.subtitle}` : item.title;
  if (availableWidth < BLOCK_LABEL_MIN_WIDTH) {
    return "";
  }
  if (textFits(label, availableWidth)) {
    return label;
  }
  return truncateToWidth(item.title, availableWidth);
}

function truncateToWidth(value, width) {
  const text = String(value || "");
  const maxLength = Math.max(Math.floor(width / APPROX_CHAR_WIDTH) - ELLIPSIS_LENGTH, 0);
  if (text.length <= maxLength + ELLIPSIS_LENGTH) {
    return text;
  }
  return `${text.slice(0, maxLength)}...`;
}

function needsExternalBlockLabel(item, x) {
  const label = item.subtitle ? `${item.title} · ${item.subtitle}` : item.title;
  return !textFits(label, blockWidth(item, x) - BLOCK_LABEL_SIDE_PADDING);
}

function edgeY(item) {
  const bottomEdge = item.type === "education" || item.type === "stay";
  return bottomEdge ? BLOCK_EDGE_BOTTOM_Y : BLOCK_EDGE_TOP_Y;
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
    let cursor = item.y + BLOCK_HEIGHT + LABEL_BLOCK_GAP;
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
      const lane = laneEnds.findIndex((laneEnd) => stack.x >= laneEnd + STACK_COLLISION_GAP);
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
    return wrapLabel(item.subtitle, LABEL_MAX_CHARS.block, LABEL_MAX_LINES.subtitle);
  }
  return wrapDetails(item.title, item.subtitle, LABEL_MAX_CHARS.block, LABEL_MAX_LINES.block);
}

function grantLabelLines(item) {
  return item.grants.flatMap((grant) =>
    wrapDetails(grant.title, grant.subtitle, LABEL_MAX_CHARS.grant, LABEL_MAX_LINES.block),
  );
}

function markerLabelLines(marker) {
  return wrapDetails(marker.title, marker.subtitle, LABEL_MAX_CHARS.marker, LABEL_MAX_LINES.block);
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
  if (text.length <= maxChars - ELLIPSIS_LENGTH) {
    return `${text}...`;
  }
  return `${text.slice(0, maxChars - ELLIPSIS_LENGTH)}...`;
}

function appendWrappedText(group, lines, x, y) {
  const text = group.append("text").attr("x", x).attr("y", y);
  lines.forEach((line, index) => {
    text
      .append("tspan")
      .attr("x", x)
      .attr("dy", index === 0 ? 0 : LABEL_LINE_HEIGHT)
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

function readTimelineData(element) {
  try {
    const data = JSON.parse(element.textContent || "{}");
    if (!data.range?.start || !data.range?.end || !Array.isArray(data.filters)) {
      return null;
    }
    return {
      ...data,
      items: Array.isArray(data.items) ? data.items : [],
      markers: Array.isArray(data.markers) ? data.markers : [],
    };
  } catch {
    return null;
  }
}

function setTimelineStatus(container, message) {
  const status = container.querySelector(CAREER_SELECTORS.loading);
  if (status) {
    status.textContent = message;
  }
}

function initCareerTimeline() {
  const container = document.querySelector(CAREER_SELECTORS.container);
  const dataElement = document.getElementById(CAREER_SELECTORS.data);

  if (!container || !dataElement) {
    return;
  }
  if (!window.d3) {
    setTimelineStatus(container, CAREER_MESSAGES.dependencyUnavailable);
    return;
  }

  const data = readTimelineData(dataElement);
  if (!data) {
    setTimelineStatus(container, CAREER_MESSAGES.dataUnavailable);
    return;
  }

  const state = new Set(data.filters.map((filter) => filter.id));
  const resetButton = document.querySelector(CAREER_SELECTORS.reset);
  const filterButtons = document.querySelectorAll(CAREER_SELECTORS.filter);
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
  window.addEventListener("resize", () => {
    window.requestAnimationFrame(() => {
      timeline.updateDisplaySize();
      timeline.scrollToLatest();
    });
  });
  timeline.render();
  scheduleLatestScroll(timeline);
}

function scheduleLatestScroll(timeline) {
  const scroll = () => timeline.scrollToLatest();
  window.requestAnimationFrame(() => {
    scroll();
    window.requestAnimationFrame(scroll);
  });
  window.setTimeout(scroll, 150);
  window.addEventListener("load", scroll, { once: true });
}

initCareerTimeline();
