(() => {
  const mapElement = document.querySelector("[data-collaboration-map]");
  const dataElement = document.getElementById("collaboration-map-data");

  if (!mapElement || !dataElement || !window.d3 || !window.topojson) {
    return;
  }

  const data = JSON.parse(dataElement.textContent);
  const width = 960;
  const height = 500;
  const svg = window.d3
    .select(mapElement)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("aria-hidden", "true");
  const baseLayer = svg.append("g").attr("class", "map-base-layer");
  const pointLayer = svg.append("g").attr("class", "map-point-layer");

  const projection = window.d3.geoNaturalEarth1().fitExtent(
    [
      [14, 18],
      [width - 14, height - 18],
    ],
    { type: "Sphere" },
  );
  const geoPath = window.d3.geoPath(projection);
  const graticule = window.d3.geoGraticule10();
  const publicationNodes = prepareMapNodes(data.publication_nodes || [], projection);
  const stayNodes = prepareMapNodes(data.stay_nodes || [], projection);
  const zoomBehavior = window.d3
    .zoom()
    .scaleExtent([1, 10])
    .translateExtent([
      [-width, -height],
      [width * 2, height * 2],
    ])
    .on("zoom", (event) => applyMapTransform(baseLayer, pointLayer, event.transform));

  svg.call(zoomBehavior);
  baseLayer.append("path").datum({ type: "Sphere" }).attr("class", "map-sphere").attr("d", geoPath);
  baseLayer.append("path").datum(graticule).attr("class", "map-graticule").attr("d", geoPath);

  fetch("https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json")
    .then((response) => response.json())
    .then((world) => {
      const countries = window.topojson.feature(world, world.objects.countries);
      baseLayer
        .append("g")
        .attr("class", "map-countries")
        .selectAll("path")
        .data(countries.features)
        .join("path")
        .attr("class", "map-country")
        .attr("d", geoPath);

      drawPublicationNodes(pointLayer, publicationNodes);
      drawStayMarkers(pointLayer, stayNodes);
      svg.call(
        zoomBehavior.transform,
        fitPointsTransform([...publicationNodes, ...stayNodes], width, height),
      );
      mapElement.classList.add("loaded");
    })
    .catch(() => {
      mapElement.querySelector(".map-loading").textContent = "Map data unavailable";
    });
})();

function prepareMapNodes(nodes, projection) {
  return nodes
    .map((node) => {
      const point = projection([node.longitude, node.latitude]);
      return point ? { ...node, x: point[0], y: point[1] } : null;
    })
    .filter(Boolean);
}

function fitPointsTransform(nodes, width, height) {
  if (!nodes.length) {
    return window.d3.zoomIdentity;
  }

  const padding = 86;
  const minX = window.d3.min(nodes, (node) => node.x);
  const maxX = window.d3.max(nodes, (node) => node.x);
  const minY = window.d3.min(nodes, (node) => node.y);
  const maxY = window.d3.max(nodes, (node) => node.y);
  const dx = Math.max(maxX - minX, 1);
  const dy = Math.max(maxY - minY, 1);
  const scale = Math.max(
    1,
    Math.min(7.5, Math.min((width - padding * 2) / dx, (height - padding * 2) / dy)),
  );
  const x = width / 2 - scale * ((minX + maxX) / 2);
  const y = height / 2 - scale * ((minY + maxY) / 2);

  return window.d3.zoomIdentity.translate(x, y).scale(scale);
}

function applyMapTransform(baseLayer, pointLayer, transform) {
  baseLayer.attr("transform", transform);
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
        `${node.city}, ${node.country} · ${node.publication_count} ${
          node.publication_count === 1 ? "publication" : "publications"
        }`,
    );
}

function drawStayMarkers(layer, nodes) {
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
    .attr("y2", -22);
  markers
    .append("line")
    .attr("class", "stay-stem")
    .attr("x1", 0)
    .attr("y1", 0)
    .attr("x2", 0)
    .attr("y2", -22);
  markers.append("circle").attr("cx", 0).attr("cy", -27).attr("r", 5.4);
  markers
    .append("text")
    .attr("class", "stay-month-label")
    .attr("x", 8)
    .attr("y", -24)
    .text((node) => `${node.months} mo`);
  markers
    .append("title")
    .text(
      (node) =>
        `${node.city}, ${node.country} · ${node.months} ${
          node.months === 1 ? "month" : "months"
        } in research stay`,
    );
}
