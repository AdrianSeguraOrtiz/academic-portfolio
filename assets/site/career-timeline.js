const CAREER_SELECTORS = {
  container: "[data-career-timeline]",
  data: "career-timeline-data",
  filter: "[data-career-filter]",
  loading: ".map-loading",
  reset: "[data-career-reset]",
  scroller: ".career-timeline-scroll",
  zoomIn: "[data-career-zoom-in]",
  zoomOut: "[data-career-zoom-out]",
};

const CAREER_MESSAGES = {
  dataUnavailable: "Career timeline data unavailable",
  dependencyUnavailable: "Career timeline library unavailable",
};

// Layout constants keep the SVG timeline stable while making visual tuning explicit.
const TIMELINE_MIN_WIDTH = 1280;
const TIMELINE_WIDTH_PER_YEAR = 170;
const TIMELINE_MIN_HEIGHT = 700;
const TIMELINE_MARGIN = { top: 26, right: 42, bottom: 46, left: 110 };
const TIMELINE_FALLBACK_YEAR_SPAN = 8;
const TIMELINE_MIN_YEAR_SPAN = 6;
const TIMELINE_RESET_DURATION = 250;
const TIMELINE_ZOOM_EXTENT = [1, 7];
const COMPACT_TIMELINE_MIN_WIDTH = 320;
const COMPACT_TIMELINE_MAX_SCALE = 2.4;
const TIMELINE_ZOOM_STEP = 1.25;
const AXIS_YEAR_LABEL_OFFSET = 30;
const AXIS_TOP_GAP = 30;
const AXIS_BOTTOM_GAP = 50;
const PAST_PADDING_MONTHS = 4;
const FUTURE_PADDING_MONTHS = 16;
const FUTURE_LABEL_MONTHS = 4;
const FUTURE_LABEL_X_FALLBACK = 20;
const BLOCK_HEIGHT = 26;
const BLOCK_LANE_GAP = 12;
const BLOCK_RADIUS = 9;
const BLOCK_MIN_WIDTH = 4;
const BLOCK_INNER_LABEL_X = 8;
const BLOCK_INNER_LABEL_Y = 17;
const BLOCK_EDGE_TOP_Y = -3;
const BLOCK_EDGE_BOTTOM_Y = 29;
const BLOCK_LABEL_SIDE_PADDING = 16;
const BLOCK_LABEL_MIN_WIDTH = 44;
const MARKER_LABEL_Y_OFFSET = -5;
const MARKER_LINE_GAP = 10;
const MARKER_LABEL_WIDTH = 190;
const STACK_COLLISION_GAP = 24;
const APPROX_CHAR_WIDTH = 6.3;
const ELLIPSIS_LENGTH = 3;
const DATE_ISO_LENGTH = 10;
const LANE_LABELS = [
  { key: "certification", text: "Certifications" },
  { key: "experience", text: "Experience" },
  { key: "education", text: "Education" },
  { key: "stay", text: "Research Stays" },
  { key: "honor", text: "Honors" },
];
const LABEL_LINE_HEIGHT = 12;
const LABEL_PIECE_GAP = 8;
const LABEL_TRACK_GAP = 12;
const LABEL_AREA_GAP = 14;
const TIMELINE_SECTION_GAP = 28;
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
    this.height = TIMELINE_MIN_HEIGHT;
    this.margin = TIMELINE_MARGIN;
    this.baseline = 0;
    this.compactScale = 1;
    this.displayWidth = compactTimelineDisplayWidth(this.width, this.container, this.compactScale);
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
    this.updateScrollerMode();
  }

  updateDisplaySize() {
    this.displayWidth = compactTimelineDisplayWidth(this.width, this.container, this.compactScale);
    this.displayHeight = Math.round(this.height * (this.displayWidth / this.width));
    this.container.style.width = `${this.displayWidth}px`;
    this.container.style.setProperty("--timeline-display-height", `${this.displayHeight}px`);
    this.svg.attr("width", this.displayWidth).attr("height", this.displayHeight);
    this.updateScrollerMode();
  }

  updateScrollerMode() {
    const scroller = this.container.closest(CAREER_SELECTORS.scroller);
    scroller?.classList.toggle(
      "is-zoomed",
      this.displayWidth > scroller.clientWidth + 1,
    );
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

    const layout = buildTimelineLayout(items, markers, x, this.margin);
    this.height = layout.height;
    this.baseline = layout.baseline;
    this.zoom.translateExtent([
      [0, 0],
      [this.width, this.height],
    ]);
    this.svg.attr("viewBox", `0 0 ${this.width} ${this.height}`);
    this.updateDisplaySize();

    this.drawAxis(x);
    this.drawLaneLabels(x, layout.labels);
    this.drawMarkerLines(x, layout.markers);
    this.drawBlocks(x, layout.blocks, layout.labelStacks);
    this.drawMarkerSymbols(x, layout.markers);
  }

  resetZoom() {
    this.compactScale = 1;
    this.updateDisplaySize();
    this.svg
      .transition()
      .duration(TIMELINE_RESET_DURATION)
      .call(this.zoom.transform, window.d3.zoomIdentity);
    this.scrollToLatest();
  }

  zoomBy(factor) {
    this.compactScale = clamp(this.compactScale * factor, 1, COMPACT_TIMELINE_MAX_SCALE);
    this.updateDisplaySize();
    this.scrollToLatest();
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
      .attr("y1", this.margin.top)
      .attr("y2", this.height - this.margin.bottom);
    tickGroup
      .selectAll("text")
      .data(ticks)
      .join("text")
      .attr("x", (tick) => x(tick))
      .attr("y", this.baseline + AXIS_YEAR_LABEL_OFFSET)
      .text((tick) => tick.getFullYear());
  }

  drawLaneLabels(x, layoutLabels) {
    const labels = layoutLabels.map((label) => ({
      ...label,
      text:
        this.data.labels?.[label.key]
        || LANE_LABELS.find((candidate) => candidate.key === label.key)?.text
        || label.key,
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

  drawBlocks(x, blockData, labelStacks) {
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

    blocks.append("title").text((item) => blockTitle(item, this.data.labels || {}));
  }

  drawMarkerLines(x, markers) {
    const markerGroups = this.root
      .append("g")
      .attr("class", "career-marker-line-layer")
      .selectAll("g")
      .data(markers)
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
  }

  drawMarkerSymbols(x, markers) {
    const markerGroups = this.root
      .append("g")
      .attr("class", "career-marker-symbol-layer")
      .selectAll("g")
      .data(markers)
      .join("g")
      .attr("class", (marker) => `career-marker ${marker.type}`)
      .attr("transform", (marker) => `translate(${x(parseCareerDate(marker.date))},0)`);

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
          `translate(${marker.labelX - marker.xPosition},${marker.yAnchor + MARKER_LABEL_Y_OFFSET})`,
        );
      appendWrappedText(labelGroup, markerLabelLines(marker), 0, 0);
    });

    markerGroups.append("title").text((marker) => markerTitle(marker));
  }

  scrollToLatest() {
    const scroller = this.container.closest(CAREER_SELECTORS.scroller);
    if (scroller) {
      if (this.compactScale <= 1) {
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

function compactTimelineDisplayWidth(width, container, compactScale = 1) {
  const scroller = container.closest(CAREER_SELECTORS.scroller);
  const viewportWidth = scroller?.clientWidth || window.innerWidth || COMPACT_TIMELINE_MIN_WIDTH;
  const baseWidth = Math.min(width, Math.max(viewportWidth, COMPACT_TIMELINE_MIN_WIDTH));
  return Math.round(Math.min(width, baseWidth * compactScale));
}

function shouldHandleTimelineZoom(event) {
  if (String(event.type || "").startsWith("touch")) {
    return false;
  }
  return (!event.ctrlKey || event.type === "wheel") && !event.button;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function offsetDate(value, months) {
  const copy = new Date(value.getTime());
  copy.setMonth(copy.getMonth() + months);
  return copy;
}

function isMonthPrecision(value) {
  return /^\d{4}-\d{2}$/.test(String(value || ""));
}

function durationEndDate(item) {
  const end = parseCareerDate(item.end);
  return item.is_current || isMonthPrecision(item.end_label) ? offsetDate(end, 1) : end;
}

function buildTimelineLayout(items, markers, x, margin) {
  const blocks = [];
  const labelStacks = [];
  const positionedMarkers = [];
  const labels = [];
  let cursor = margin.top;

  const certificationBand = layoutMarkerBand(
    markers.filter((marker) => marker.type === "certification"),
    x,
    cursor,
  );
  if (certificationBand.items.length) {
    positionedMarkers.push(...certificationBand.items);
    labels.push({ key: "certification", y: certificationBand.center });
    cursor = certificationBand.bottom + TIMELINE_SECTION_GAP;
  }

  const experienceBand = layoutBlockBand(
    items.filter((item) => item.type === "experience"),
    x,
    cursor,
  );
  if (experienceBand.blocks.length) {
    blocks.push(...experienceBand.blocks);
    labelStacks.push(...experienceBand.labelStacks);
    labels.push({ key: "experience", y: experienceBand.center });
    cursor = experienceBand.bottom;
  }

  const baseline = cursor + AXIS_TOP_GAP;
  cursor = baseline + AXIS_BOTTOM_GAP;

  for (const type of ["education", "stay"]) {
    const band = layoutBlockBand(
      items.filter((item) => item.type === type),
      x,
      cursor,
    );
    if (!band.blocks.length) {
      continue;
    }
    blocks.push(...band.blocks);
    labelStacks.push(...band.labelStacks);
    labels.push({ key: type, y: band.center });
    cursor = band.bottom + TIMELINE_SECTION_GAP;
  }

  const honorBand = layoutMarkerBand(
    markers.filter((marker) => marker.type === "honor"),
    x,
    cursor,
  );
  if (honorBand.items.length) {
    positionedMarkers.push(...honorBand.items);
    labels.push({ key: "honor", y: honorBand.center });
    cursor = honorBand.bottom;
  }

  return {
    baseline,
    blocks,
    height: Math.max(cursor + margin.bottom, TIMELINE_MIN_HEIGHT),
    labels,
    labelStacks,
    markers: positionedMarkers,
  };
}

function layoutBlockBand(items, x, startY) {
  if (!items.length) {
    return emptyLayoutBand(startY);
  }

  const laneItems = assignLanes(items);
  const labelDefinitions = laneItems.flatMap((item) => itemLabelStackDefinitions(item, x));
  const aboveDefinitions = labelDefinitions.filter((stack) => stack.side === "above");
  const belowDefinitions = labelDefinitions.filter((stack) => stack.side === "below");
  const aboveLayout = positionLabelTracks(aboveDefinitions, startY);
  const blockTop = aboveDefinitions.length
    ? aboveLayout.bottom + LABEL_AREA_GAP
    : startY;
  const laneCount = Math.max(...laneItems.map((item) => item.lane)) + 1;
  const blockAreaHeight = laneCount * BLOCK_HEIGHT + (laneCount - 1) * BLOCK_LANE_GAP;
  const blocks = laneItems.map((item) => ({
    ...item,
    y: blockTop + item.lane * (BLOCK_HEIGHT + BLOCK_LANE_GAP),
  }));
  const blockBottom = blockTop + blockAreaHeight;
  const belowStart = belowDefinitions.length
    ? blockBottom + LABEL_AREA_GAP
    : blockBottom;
  const belowLayout = positionLabelTracks(belowDefinitions, belowStart);
  const bottom = belowDefinitions.length ? belowLayout.bottom : blockBottom;

  return {
    blocks,
    bottom,
    center: startY + (bottom - startY) / 2,
    labelStacks: [...aboveLayout.stacks, ...belowLayout.stacks],
  };
}

function layoutMarkerBand(markers, x, startY) {
  if (!markers.length) {
    return { items: [], bottom: startY, center: startY };
  }

  const candidates = markers.map((marker) => {
    const xPosition = x(parseCareerDate(marker.date));
    const labelX = clampedLabelX(xPosition + 10, x, MARKER_LABEL_WIDTH);
    return {
      ...marker,
      x: labelX,
      lines: markerLabelLines(marker),
      labelX,
      width: MARKER_LABEL_WIDTH,
      xPosition,
    };
  });
  const tracked = assignHorizontalTracks(candidates);
  const trackHeights = trackMaximums(
    tracked,
    (marker) => Math.max(marker.lines.length * LABEL_LINE_HEIGHT + 8, 24),
  );
  const trackTops = trackOffsets(trackHeights, startY);
  const items = tracked.map((marker) => ({
    ...marker,
    yAnchor: trackTops[marker.track] + 10,
  }));
  const bottom = trackBottom(trackHeights, startY);

  return {
    items,
    bottom,
    center: startY + (bottom - startY) / 2,
  };
}

function emptyLayoutBand(startY) {
  return {
    blocks: [],
    bottom: startY,
    center: startY,
    labelStacks: [],
  };
}

function assignLanes(items) {
  const lanes = [];
  return [...items]
    .sort((a, b) => parseCareerDate(a.start) - parseCareerDate(b.start))
    .map((item) => {
      const start = parseCareerDate(item.start).getTime();
      const end = durationEndDate(item).getTime();
      const lane = lanes.findIndex((laneEnd) => start >= laneEnd);
      if (lane === -1) {
        lanes.push(end);
        return { ...item, lane: lanes.length - 1 };
      }
      lanes[lane] = end;
      return { ...item, lane };
    });
}

function blockWidth(item, x) {
  return Math.max(x(durationEndDate(item)) - x(parseCareerDate(item.start)), BLOCK_MIN_WIDTH);
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

function itemLabelStackDefinitions(item, x) {
  const blockLines = externalBlockLabelLines(item, x);
  const grantPieces = grantLabelPieces(item);
  const stacks = [];

  if (item.type === "experience") {
    const pieces = [
      ...grantPieces,
      ...(blockLines.length ? [{ kind: "block", lines: blockLines }] : []),
    ];
    const stack = labelStackDefinition(item, x, "above", pieces);
    return stack ? [stack] : [];
  }

  if (item.type === "stay") {
    const blockStack = labelStackDefinition(
      item,
      x,
      "above",
      blockLines.length ? [{ kind: "block", lines: blockLines }] : [],
    );
    const grantStack = labelStackDefinition(
      item,
      x,
      "below",
      grantPieces,
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
    ...grantPieces,
  ];
  const stack = labelStackDefinition(item, x, "below", pieces);
  return stack ? [stack] : [];
}

function externalBlockLabelLines(item, x) {
  if (!needsExternalBlockLabel(item, x)) {
    return [];
  }
  return blockLabelLines(item, x);
}

function labelStackDefinition(item, x, side, pieces) {
  if (!pieces.length) {
    return null;
  }

  const rawX = x(parseCareerDate(item.start)) + 8;
  return {
    height: stackHeight(pieces),
    side,
    type: item.type,
    x: clampedLabelX(rawX, x, LABEL_WIDTH),
    width: LABEL_WIDTH,
    pieces,
  };
}

function positionLabelTracks(stacks, startY) {
  if (!stacks.length) {
    return { bottom: startY, stacks: [] };
  }

  const tracked = assignHorizontalTracks(stacks);
  const trackHeights = trackMaximums(tracked, (stack) => stack.height);
  const trackTops = trackOffsets(
    trackHeights,
    startY,
    stacks[0].side === "above",
  );
  return {
    bottom: trackBottom(trackHeights, startY),
    stacks: tracked.map((stack) => ({
      ...stack,
      pieces: positionStackPieces(stack.pieces, trackTops[stack.track]),
    })),
  };
}

function assignHorizontalTracks(items) {
  const trackEnds = [];
  return [...items]
    .sort((a, b) => a.x - b.x)
    .map((item) => {
      const availableTrack = trackEnds.findIndex(
        (trackEnd) => item.x >= trackEnd + STACK_COLLISION_GAP,
      );
      const track = availableTrack === -1 ? trackEnds.length : availableTrack;
      trackEnds[track] = item.x + item.width;
      return { ...item, track };
    });
}

function trackMaximums(items, measure) {
  const maximums = [];
  items.forEach((item) => {
    maximums[item.track] = Math.max(maximums[item.track] || 0, measure(item));
  });
  return maximums;
}

function trackOffsets(trackHeights, startY, reverse = false) {
  const offsets = [];
  if (reverse) {
    let cursor = trackBottom(trackHeights, startY);
    trackHeights.forEach((height, index) => {
      cursor -= height;
      offsets[index] = cursor;
      cursor -= LABEL_TRACK_GAP;
    });
    return offsets;
  }

  let cursor = startY;
  trackHeights.forEach((height, index) => {
    offsets[index] = cursor;
    cursor += height + LABEL_TRACK_GAP;
  });
  return offsets;
}

function trackBottom(trackHeights, startY) {
  if (!trackHeights.length) {
    return startY;
  }
  return startY
    + trackHeights.reduce((total, height) => total + height, 0)
    + (trackHeights.length - 1) * LABEL_TRACK_GAP;
}

function positionStackPieces(pieces, top) {
  let cursor = top + LABEL_LINE_HEIGHT;
  return pieces.map((piece) => {
    const positioned = { ...piece, y: cursor };
    cursor += piece.lines.length * LABEL_LINE_HEIGHT + LABEL_PIECE_GAP;
    return positioned;
  });
}

function stackHeight(pieces) {
  return pieces.reduce(
    (height, piece, index) =>
      height + piece.lines.length * LABEL_LINE_HEIGHT + (index ? LABEL_PIECE_GAP : 0),
    0,
  );
}

function clampedLabelX(value, x, width) {
  const [rangeStart, rangeEnd] = x.range();
  return clamp(value, rangeStart, rangeEnd - width);
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

function grantLabelPieces(item) {
  return item.grants.map((grant) => ({
    kind: "grant",
    lines: wrapDetails(
      grant.title,
      grant.subtitle,
      LABEL_MAX_CHARS.grant,
      LABEL_MAX_LINES.block,
    ),
  }));
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

function blockTitle(item, labels = {}) {
  const lines = [`${item.title}`, `${item.date_label}`];
  if (item.subtitle) {
    lines.push(item.subtitle);
  }
  if (item.grants.length) {
    lines.push(`${labels.grant || "Grants"}: ${item.grants.map((grant) => grant.title).join(", ")}`);
  }
  if (item.honors.length) {
    lines.push(`${labels.honor || "Honors"}: ${item.honors.map((honor) => honor.title).join(", ")}`);
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
    setTimelineStatus(
      container,
      container.dataset.dependencyMessage || CAREER_MESSAGES.dependencyUnavailable,
    );
    return;
  }

  const data = readTimelineData(dataElement);
  if (!data) {
    setTimelineStatus(
      container,
      container.dataset.unavailableMessage || CAREER_MESSAGES.dataUnavailable,
    );
    return;
  }

  const state = new Set(data.filters.map((filter) => filter.id));
  const resetButton = document.querySelector(CAREER_SELECTORS.reset);
  const zoomInButton = document.querySelector(CAREER_SELECTORS.zoomIn);
  const zoomOutButton = document.querySelector(CAREER_SELECTORS.zoomOut);
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
  zoomInButton?.addEventListener("click", () => timeline.zoomBy(TIMELINE_ZOOM_STEP));
  zoomOutButton?.addEventListener("click", () => timeline.zoomBy(1 / TIMELINE_ZOOM_STEP));
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
