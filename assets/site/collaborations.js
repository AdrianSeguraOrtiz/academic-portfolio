const COLLABORATION_SELECTORS = {
  data: "collaboration-map-data",
  loading: ".map-loading",
  map: "[data-collaboration-map]",
};

const WORLD_ATLAS_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

// Layout constants keep the collaboration map visually stable across rebuilds.
const MAP_LAYOUT = {
  height: 540,
  width: 960,
  projectionPadding: {
    bottom: 18,
    left: 14,
    right: 14,
    top: 18,
  },
  pointFitMaxScale: 7.5,
  pointFitPadding: 86,
  stayMarker: {
    circleRadius: 5.4,
    circleY: -27,
    labelX: 8,
    labelY: -24,
    stemY: -22,
  },
  workMarker: {
    holeRadius: 2.5,
    labelX: 10,
    labelY: -22,
    path:
      "M0,0 L-7,-20 A7,7 0 1 1 7,-20 Z",
  },
  zoomExtentFactor: 2,
  zoomMax: 10,
  zoomMin: 1,
};

const MAP_MESSAGES = {
  dataUnavailable: "Map data unavailable",
  dependencyUnavailable: "Map libraries unavailable",
};

function initCollaborationMap() {
  const mapElement = document.querySelector(COLLABORATION_SELECTORS.map);
  const dataElement = document.getElementById(COLLABORATION_SELECTORS.data);

  if (!mapElement || !dataElement) {
    return;
  }
  if (!window.d3 || !window.topojson || !window.fetch) {
    setMapStatus(mapElement, MAP_MESSAGES.dependencyUnavailable);
    return;
  }

  const data = readJsonScript(dataElement);
  if (!data) {
    setMapStatus(mapElement, MAP_MESSAGES.dataUnavailable);
    return;
  }

  renderCollaborationMap(mapElement, data);
}

function renderCollaborationMap(mapElement, data) {
  const { height, width } = MAP_LAYOUT;
  const svg = window.d3
    .select(mapElement)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("aria-hidden", "true");
  const baseLayer = svg.append("g").attr("class", "map-base-layer");
  const pointLayer = svg.append("g").attr("class", "map-point-layer");
  const projection = buildProjection();
  const geoPath = window.d3.geoPath(projection);
  const graticule = window.d3.geoGraticule10();
  const publicationNodes = prepareMapNodes(asArray(data.publication_nodes), projection);
  const stayNodes = prepareMapNodes(asArray(data.stay_nodes), projection);
  const workNodes = prepareMapNodes(asArray(data.work_nodes), projection);
  const routeNodes = prepareRouteNodes(asArray(data.route_nodes), projection);
  const zoomBehavior = buildZoomBehavior(baseLayer, pointLayer);

  svg.call(zoomBehavior);
  baseLayer.append("path").datum({ type: "Sphere" }).attr("class", "map-sphere").attr("d", geoPath);
  baseLayer.append("path").datum(graticule).attr("class", "map-graticule").attr("d", geoPath);

  loadCountries()
    .then((countries) => {
      drawCountries(baseLayer, countries, geoPath);
      drawStayRoutes(pointLayer, routeNodes);
      drawPublicationNodes(pointLayer, publicationNodes);
      drawStayMarkers(pointLayer, stayNodes);
      drawWorkMarkers(pointLayer, workNodes);
      svg.call(
        zoomBehavior.transform,
        fitPointsTransform([...publicationNodes, ...stayNodes, ...workNodes], width, height),
      );
      mapElement.classList.add("loaded");
    })
    .catch(() => setMapStatus(mapElement, MAP_MESSAGES.dataUnavailable));
}

function readJsonScript(element) {
  try {
    return JSON.parse(element.textContent || "{}");
  } catch {
    return null;
  }
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function setMapStatus(mapElement, message) {
  const status = mapElement.querySelector(COLLABORATION_SELECTORS.loading);
  if (status) {
    status.textContent = message;
  }
}

function buildProjection() {
  const { height, projectionPadding, width } = MAP_LAYOUT;
  return window.d3.geoNaturalEarth1().fitExtent(
    [
      [projectionPadding.left, projectionPadding.top],
      [width - projectionPadding.right, height - projectionPadding.bottom],
    ],
    { type: "Sphere" },
  );
}

function buildZoomBehavior(baseLayer, pointLayer) {
  const { height, width, zoomExtentFactor, zoomMax, zoomMin } = MAP_LAYOUT;
  return window.d3
    .zoom()
    .scaleExtent([zoomMin, zoomMax])
    .translateExtent([
      [-width, -height],
      [width * zoomExtentFactor, height * zoomExtentFactor],
    ])
    .on("zoom", (event) => applyMapTransform(baseLayer, pointLayer, event.transform));
}

function loadCountries() {
  return window.fetch(WORLD_ATLAS_URL).then((response) => {
    if (!response.ok) {
      throw new Error(`World atlas request failed: ${response.status}`);
    }
    return response.json();
  });
}

function drawCountries(baseLayer, world, geoPath) {
  const countries = window.topojson.feature(world, world.objects.countries);
  baseLayer
    .append("g")
    .attr("class", "map-countries")
    .selectAll("path")
    .data(countries.features)
    .join("path")
    .attr("class", "map-country")
    .attr("d", geoPath);
}

function prepareMapNodes(nodes, projection) {
  return nodes
    .map((node) => {
      const point = projection([node.longitude, node.latitude]);
      return point ? { ...node, x: point[0], y: point[1] } : null;
    })
    .filter(Boolean);
}

function prepareRouteNodes(nodes, projection) {
  const routeNodes = nodes
    .map((node) => {
      const origin = projection([node.origin_longitude, node.origin_latitude]);
      const destination = projection([node.destination_longitude, node.destination_latitude]);
      return origin && destination
        ? {
            ...node,
            originX: origin[0],
            originY: origin[1],
            destinationX: destination[0],
            destinationY: destination[1],
          }
        : null;
    })
    .filter(Boolean);
  assignRouteOffsets(routeNodes);
  return routeNodes;
}

function assignRouteOffsets(nodes) {
  const groups = new Map();
  nodes.forEach((node) => {
    const key = [
      Math.round(node.originX),
      Math.round(node.originY),
      Math.round(node.destinationX),
      Math.round(node.destinationY),
    ].join(":");
    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key).push(node);
  });
  groups.forEach((routes) => {
    routes.forEach((route, index) => {
      route.curveOffset = (index - (routes.length - 1) / 2) * 22;
    });
  });
}

function fitPointsTransform(nodes, width, height) {
  if (!nodes.length) {
    return window.d3.zoomIdentity;
  }

  const { pointFitMaxScale, pointFitPadding } = MAP_LAYOUT;
  const minX = window.d3.min(nodes, (node) => node.x);
  const maxX = window.d3.max(nodes, (node) => node.x);
  const minY = window.d3.min(nodes, (node) => node.y);
  const maxY = window.d3.max(nodes, (node) => node.y);
  const dx = Math.max(maxX - minX, 1);
  const dy = Math.max(maxY - minY, 1);
  const scale = Math.max(
    1,
    Math.min(
      pointFitMaxScale,
      Math.min((width - pointFitPadding * 2) / dx, (height - pointFitPadding * 2) / dy),
    ),
  );
  const x = width / 2 - scale * ((minX + maxX) / 2);
  const y = height / 2 - scale * ((minY + maxY) / 2);

  return window.d3.zoomIdentity.translate(x, y).scale(scale);
}

function applyMapTransform(baseLayer, pointLayer, transform) {
  baseLayer.attr("transform", transform);
  pointLayer
    .selectAll(".stay-route-line")
    .attr("d", (node) => routePath(node, transform));
  pointLayer
    .selectAll(".publication-map-node")
    .attr("cx", (node) => transform.applyX(node.x))
    .attr("cy", (node) => transform.applyY(node.y));
  pointLayer
    .selectAll(".stay-map-marker")
    .attr("transform", (node) => {
      const x = transform.applyX(node.x);
      const y = transform.applyY(node.y);
      return `translate(${x},${y})`;
    });
  pointLayer
    .selectAll(".work-map-marker")
    .attr("transform", (node) => {
      const x = transform.applyX(node.x);
      const y = transform.applyY(node.y);
      return `translate(${x},${y})`;
    });
}

function drawStayRoutes(layer, nodes) {
  const routes = layer
    .append("g")
    .attr("class", "stay-route-layer")
    .selectAll("g")
    .data(nodes)
    .join("g")
    .attr("class", "stay-route");

  routes
    .append("path")
    .attr("class", "stay-route-line stay-route-path")
    .attr("d", (node) => routePath(node));
  routes.append("title").text((node) => node.label);
}

function routePath(node, transform = window.d3.zoomIdentity) {
  const x1 = transform.applyX(node.originX);
  const y1 = transform.applyY(node.originY);
  const x2 = transform.applyX(node.destinationX);
  const y2 = transform.applyY(node.destinationY);
  const dx = x2 - x1;
  const dy = y2 - y1;
  const distance = Math.hypot(dx, dy) || 1;
  const curve = Math.min(90, Math.max(34, distance * 0.2)) + (node.curveOffset || 0);
  const controlX = (x1 + x2) / 2 + (-dy / distance) * curve;
  const controlY = (y1 + y2) / 2 + (dx / distance) * curve;
  return `M${x1},${y1} Q${controlX},${controlY} ${x2},${y2}`;
}

function drawPublicationNodes(layer, nodes) {
  layer
    .append("g")
    .attr("class", "publication-layer")
    .selectAll("circle")
    .data(nodes)
    .join("circle")
    .attr("class", "publication-map-node")
    .attr("cx", (node) => node.x)
    .attr("cy", (node) => node.y)
    .attr("r", (node) => node.radius)
    .append("title")
    .text(
      (node) =>
        `${node.city}, ${node.country} · ${node.publication_label || node.publication_count}`,
    );
}

function drawStayMarkers(layer, nodes) {
  const { circleRadius, circleY, labelX, labelY, stemY } = MAP_LAYOUT.stayMarker;
  const markers = layer
    .append("g")
    .attr("class", "stay-layer")
    .selectAll("g")
    .data(nodes)
    .join("g")
    .attr("class", "stay-map-marker")
    .attr("transform", (node) => `translate(${node.x},${node.y})`);

  markers
    .append("line")
    .attr("class", "stay-stem-halo")
    .attr("x1", 0)
    .attr("y1", 0)
    .attr("x2", 0)
    .attr("y2", stemY);
  markers
    .append("line")
    .attr("class", "stay-stem")
    .attr("x1", 0)
    .attr("y1", 0)
    .attr("x2", 0)
    .attr("y2", stemY);
  markers.append("circle").attr("cx", 0).attr("cy", circleY).attr("r", circleRadius);
  markers
    .selectAll("text")
    .data((node) => stayLabels(node))
    .join("text")
    .attr("class", "stay-month-label")
    .attr("x", labelX)
    .attr("y", (_stay, index) => labelY + index * 15)
    .text((stay) => stay.label);
  markers
    .append("title")
    .text((node) => {
      const lines = stayLabels(node).map((stay) => stay.label);
      return `${node.city}, ${node.country}\n${lines.join("\n")}`;
    });
}

function stayLabels(node) {
  const stays = asArray(node.stays);
  if (stays.length) {
    return stays;
  }
  return [{ label: `${node.months} mo` }];
}

function drawWorkMarkers(layer, nodes) {
  const { holeRadius, labelX, labelY, path } = MAP_LAYOUT.workMarker;
  const markers = layer
    .append("g")
    .attr("class", "work-layer")
    .selectAll("g")
    .data(nodes)
    .join("g")
    .attr("class", "work-map-marker")
    .attr("transform", (node) => `translate(${node.x},${node.y})`);

  markers.append("path").attr("class", "work-marker-pin-halo").attr("d", path);
  markers.append("path").attr("class", "work-marker-pin").attr("d", path);
  markers
    .append("circle")
    .attr("class", "work-marker-hole")
    .attr("cx", 0)
    .attr("cy", -20)
    .attr("r", holeRadius);
  markers
    .selectAll("text")
    .data((node) => workLabels(node))
    .join("text")
    .attr("class", "work-label")
    .attr("x", labelX)
    .attr("y", (_label, index) => labelY + index * 15)
    .text((label) => label);
  markers.append("title").text((node) => {
    const lines = [`${node.city}, ${node.country}`, ...workLabels(node)];
    asArray(node.appointments).forEach((appointment) => {
      const titles = asArray(appointment.titles).join("; ");
      if (titles) {
        lines.push(`${appointment.organization}: ${titles}`);
      }
    });
    return lines.join("\n");
  });
}

function workLabels(node) {
  return asArray(node.labels);
}

initCollaborationMap();
