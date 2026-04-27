"""
genset_pipeline.py
==================
Substation-finder pipeline for the Genset tab.

Replicates QGIS "Shortest Path (Point to Point)" — including proper virtual
edge injection for off-road points — using:

  - OSMnx    : downloads the OSM road network for the area of interest
  - NetworkX : Dijkstra's algorithm on an undirected road graph
  - Shapely  : geometry projection / edge-splitting

WHY UNDIRECTED?
  Road direction is irrelevant for cable-laying. A conduit follows the road
  corridor regardless of traffic flow, so we convert the directed OSM graph
  to undirected before routing (same as QGIS Shortest Path with no
  direction constraint / QNEAT3 "Both directions").

OFF-ROAD POINT HANDLING — Virtual Edge Injection (Option A / QNEAT3 method)
  A cell site or substation is rarely sitting on a road-graph node.  Simply
  snapping to the nearest node (nearest_nodes) ignores the gap between the
  point and the road, understating the distance.

  Instead, for each off-road point we:
    1. Find the nearest *edge* (u → v) in the graph.
    2. Project the point onto that edge using Shapely to get the foot F
       (the perpendicular/closest point on the edge geometry).
    3. Split edge (u, v) into (u, F) and (F, v), preserving curve geometry
       and recalculating lengths in metres with Haversine.
    4. Add the original off-road point P as a new virtual node.
    5. Connect P → F with a short virtual edge of length haversine(P, F).
    6. Dijkstra runs from the site virtual node to the substation virtual node,
       so both the off-road tails ARE included in the reported distance.
    7. Work is done on a copy of the graph — the shared graph is never mutated.

  This is exactly what QGIS QNEAT3 does when you feed it a start/end point
  that is not on the network.
"""

import copy
import math
import logging
import time
from typing import Optional

import requests
import networkx as nx
import osmnx as ox
from shapely.geometry import LineString, Point
from shapely.ops import substring, mapping

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────────
OVERPASS_URL     = "https://overpass-api.de/api/interpreter"
DEFAULT_MAX_DIST = 2000       # metres — 2 km threshold
SEARCH_RADIUS    = 3500       # Overpass query radius (wider than threshold)
OVERPASS_TIMEOUT = 25         # seconds
OSM_GRAPH_BUFFER = 500        # extra metres padding around bbox
OVERPASS_RETRIES = 2

# Virtual node IDs — large negatives, no collision with OSM positive IDs
_VNODE_SITE_FOOT  = -1   # foot on nearest edge (site side)
_VNODE_SITE_PT    = -2   # the actual cell-site point
_VNODE_SUB_FOOT   = -3   # foot on nearest edge (substation side)
_VNODE_SUB_PT     = -4   # the actual substation point


# ── Haversine ───────────────────────────────────────────────────────────────

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres (WGS-84)."""
    R = 6_371_000.0
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p)
         * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(max(0.0, a)))


def _linestring_length_m(geom: LineString) -> float:
    """Haversine length of a lon/lat LineString in metres."""
    total = 0.0
    coords = list(geom.coords)
    for (x1, y1), (x2, y2) in zip(coords[:-1], coords[1:]):
        total += haversine_m(y1, x1, y2, x2)   # (lat, lon) order for haversine
    return total


# ── Overpass substation query ───────────────────────────────────────────────

def _fetch_substations_overpass(lat: float, lon: float,
                                 radius_m: int = SEARCH_RADIUS,
                                 timeout: int = OVERPASS_TIMEOUT) -> list:
    """
    Query Overpass for power substations within radius_m of (lat, lon).
    Returns list of {osm_id, name, operator, voltage, lat, lon, straight_dist_m}.
    """
    query = (
        f"[out:json][timeout:{timeout}];\n"
        f"(\n"
        f'  node["power"="substation"](around:{radius_m},{lat},{lon});\n'
        f'  way["power"="substation"](around:{radius_m},{lat},{lon});\n'
        f'  relation["power"="substation"](around:{radius_m},{lat},{lon});\n'
        f");\n"
        f"out center;"
    )

    for attempt in range(OVERPASS_RETRIES + 1):
        try:
            resp = requests.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=timeout + 5
            )
            resp.raise_for_status()
            elements = resp.json().get("elements", [])
            break
        except requests.exceptions.RequestException as exc:
            if attempt < OVERPASS_RETRIES:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(
                f"Overpass query failed after {OVERPASS_RETRIES + 1} attempts: {exc}"
            )

    results = []
    for el in elements:
        if el["type"] == "node":
            slat, slon = el.get("lat"), el.get("lon")
        else:
            centre = el.get("center", {})
            slat, slon = centre.get("lat"), centre.get("lon")
        if slat is None or slon is None:
            continue

        tags = el.get("tags", {})
        name = (tags.get("name") or tags.get("name:en")
                or tags.get("operator") or "Substation")

        results.append({
            "osm_id":          el["id"],
            "name":            name,
            "operator":        tags.get("operator", ""),
            "voltage":         tags.get("voltage", ""),
            "lat":             slat,
            "lon":             slon,
            "straight_dist_m": haversine_m(lat, lon, slat, slon),
        })

    return results


# ── Road graph (OSMnx) ──────────────────────────────────────────────────────

def _build_bbox(lats: list, lons: list,
                buffer_m: float = OSM_GRAPH_BUFFER) -> tuple:
    """Return (west, south, east, north) = (left, bottom, right, top) for osmnx 2.x."""
    buf = buffer_m / 111_320.0
    return (min(lons) - buf, min(lats) - buf,
            max(lons) + buf, max(lats) + buf)


def _fetch_road_graph(lats: list, lons: list) -> nx.MultiGraph:
    """
    Download the OSM drive network and return an undirected MultiGraph.

    - simplify=True   : merge degree-2 nodes, preserve curve geometry attr
    - retain_all=False: only largest weakly connected component
    - add_edge_lengths: ensure every edge has 'length' in metres
    - to_undirected   : road direction irrelevant for cable planning
    """
    bbox = _build_bbox(lats, lons)
    G_dir = ox.graph_from_bbox(
        bbox,
        network_type="drive",
        simplify=True,
        retain_all=False,
        truncate_by_edge=True,
    )
    G_dir = ox.distance.add_edge_lengths(G_dir)
    return ox.convert.to_undirected(G_dir)


# ── Virtual edge injection ──────────────────────────────────────────────────

def _edge_geometry(G: nx.MultiGraph, u: int, v: int, key: int) -> LineString:
    """Return the geometry of edge (u, v, key), synthesising if absent."""
    geom = G.edges[u, v, key].get("geometry")
    if geom is not None:
        return geom
    n1, n2 = G.nodes[u], G.nodes[v]
    return LineString([(n1["x"], n1["y"]), (n2["x"], n2["y"])])


def _inject_virtual_node(G: nx.MultiGraph,
                          lon: float, lat: float,
                          foot_node_id: int,
                          point_node_id: int) -> int:
    """
    Inject an off-road point into graph G using virtual edge injection.

    Steps (QNEAT3 / QGIS method):
      1. Find nearest edge (u, v, key).
      2. Project (lon, lat) onto that edge geometry → foot point F.
      3. Split the edge at F:
           remove (u, v, key)
           add   (u, F)  with sub-geometry and haversine length
           add   (F, v)  with sub-geometry and haversine length
      4. Add the off-road point P:
           add node P
           add edge (P, F) with length = haversine(P, F)

    Returns point_node_id (the virtual node representing the off-road point).

    Modifies G in-place — always call on a copy.
    """
    pt = Point(lon, lat)

    # ── 1. Nearest edge ──────────────────────────────────────────────────────
    u, v, key = ox.nearest_edges(G, lon, lat)
    geom = _edge_geometry(G, u, v, key)

    # ── 2. Project onto edge ─────────────────────────────────────────────────
    d_along    = geom.project(pt)           # distance along line (degrees units)
    total_len  = geom.length                # total line length (degrees units)

    # Clamp: avoid zero-length sub-edges at either end
    EPS = total_len * 1e-6
    d_clamped = max(EPS, min(total_len - EPS, d_along))

    foot      = geom.interpolate(d_clamped)
    foot_lon  = foot.x
    foot_lat  = foot.y

    dist_to_foot = haversine_m(lat, lon, foot_lat, foot_lon)   # metres

    # ── 3. Split edge ────────────────────────────────────────────────────────
    geom_before = substring(geom, 0,          d_clamped)   # u  → F
    geom_after  = substring(geom, d_clamped,  total_len)   # F  → v

    len_before = _linestring_length_m(geom_before)          # metres
    len_after  = _linestring_length_m(geom_after)           # metres

    # Copy remaining edge attributes (highway, osmid, etc.)
    base_attrs = {k: v for k, v in G.edges[u, v, key].items()
                  if k not in ("geometry", "length")}

    G.remove_edge(u, v, key)

    # Add foot node
    G.add_node(foot_node_id, x=foot_lon, y=foot_lat)

    # Add the two split edges (only if non-trivially short)
    if len_before > 0.01:
        G.add_edge(u, foot_node_id, 0,
                   geometry=geom_before, length=len_before, **base_attrs)
    else:
        # Foot collapsed onto u — connect foot to u with zero-length edge
        G.add_edge(u, foot_node_id, 0, length=0.0, **base_attrs)

    if len_after > 0.01:
        G.add_edge(foot_node_id, v, 0,
                   geometry=geom_after, length=len_after, **base_attrs)
    else:
        G.add_edge(foot_node_id, v, 0, length=0.0, **base_attrs)

    # ── 4. Add the off-road point and connect to foot ────────────────────────
    G.add_node(point_node_id, x=lon, y=lat)
    G.add_edge(
        point_node_id, foot_node_id, 0,
        geometry=LineString([(lon, lat), (foot_lon, foot_lat)]),
        length=dist_to_foot,
    )

    return point_node_id


# ── Path geometry reconstruction ────────────────────────────────────────────

def _path_to_geojson(G: nx.MultiGraph, path_nodes: list) -> Optional[dict]:
    """
    Reconstruct a GeoJSON LineString from a node sequence.
    Uses 'geometry' Shapely attrs stored on edges by OSMnx (preserving road
    curves). Falls back to straight node-to-node segments where absent.
    Coordinates are [longitude, latitude] (GeoJSON convention).
    """
    if len(path_nodes) < 2:
        return None

    coords = []

    for u, v in zip(path_nodes[:-1], path_nodes[1:]):
        edata = G.get_edge_data(u, v)
        if edata is None:
            continue

        best_key = min(edata, key=lambda k: edata[k].get("length", float("inf")))
        geom = edata[best_key].get("geometry")

        if geom is not None:
            seg = list(geom.coords)
        else:
            n1, n2 = G.nodes[u], G.nodes[v]
            seg = [(n1["x"], n1["y"]), (n2["x"], n2["y"])]

        # Avoid duplicate junction coord between consecutive edges
        if coords and seg and coords[-1] == seg[0]:
            coords.extend(seg[1:])
        else:
            coords.extend(seg)

    if len(coords) < 2:
        return None

    return mapping(LineString(coords))


# ── Main entry point ────────────────────────────────────────────────────────

def find_substations(lat: float, lon: float,
                     mode: str = "shortest",
                     max_dist_m: int = DEFAULT_MAX_DIST) -> list:
    """
    Find power substations reachable from (lat, lon) within max_dist_m via road.

    Uses OSM road network + Dijkstra with virtual edge injection for off-road
    points — identical to QGIS "Shortest Path (Point to Point)" / QNEAT3.

    Args:
        lat, lon     : cell site coords (WGS-84 degrees)
        mode         : "shortest" → single nearest result
                       "all"      → all results under threshold, sorted
        max_dist_m   : road-distance threshold in metres (default 2000)

    Returns:
        List of dicts sorted by road_dist_m:
            name, operator, voltage,
            lat, lon         (substation coords),
            road_dist_m      (float, metres),
            road_dist_km     (str, 3 d.p.),
            geometry         (GeoJSON LineString, [lon,lat] coords)
        Empty list when nothing qualifies.
    """
    if mode not in ("shortest", "all"):
        raise ValueError(f"mode must be 'shortest' or 'all', got {mode!r}")

    # ── 1. Candidate substations ─────────────────────────────────────────────
    substations = _fetch_substations_overpass(lat, lon)
    if not substations:
        return []

    # Pre-filter: crow-fly > 1.5× threshold → definitely won't pass routing
    candidates = [s for s in substations
                  if s["straight_dist_m"] <= max_dist_m * 1.5]
    if not candidates:
        return []

    # ── 2. Road graph — one fetch covers site + all candidates ───────────────
    all_lats = [lat] + [c["lat"] for c in candidates]
    all_lons = [lon] + [c["lon"] for c in candidates]

    try:
        G_shared = _fetch_road_graph(all_lats, all_lons)
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch road network: {exc}") from exc

    if len(G_shared.nodes) == 0:
        raise RuntimeError("Road graph returned no nodes for this area.")

    # ── 3. Route to each candidate ───────────────────────────────────────────
    results = []

    for sub in candidates:

        # Work on a per-route copy so virtual nodes don't accumulate
        G = G_shared.copy()

        try:
            # Inject the cell site
            site_vnode = _inject_virtual_node(
                G, lon, lat,
                foot_node_id=_VNODE_SITE_FOOT,
                point_node_id=_VNODE_SITE_PT,
            )

            # Inject the substation
            sub_vnode = _inject_virtual_node(
                G, sub["lon"], sub["lat"],
                foot_node_id=_VNODE_SUB_FOOT,
                point_node_id=_VNODE_SUB_PT,
            )

        except Exception as exc:
            logger.debug("Virtual injection failed for %s: %s", sub["name"], exc)
            continue

        if site_vnode == sub_vnode:
            continue

        try:
            path_nodes = nx.shortest_path(G, site_vnode, sub_vnode, weight="length")
            road_dist  = nx.shortest_path_length(G, site_vnode, sub_vnode, weight="length")
        except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
            logger.debug("No path to %s: %s", sub["name"], exc)
            continue

        if road_dist > max_dist_m:
            continue

        geometry = _path_to_geojson(G, path_nodes)

        results.append({
            "name":         sub["name"],
            "operator":     sub["operator"],
            "voltage":      sub["voltage"],
            "lat":          sub["lat"],
            "lon":          sub["lon"],
            "road_dist_m":  round(road_dist, 1),
            "road_dist_km": f"{road_dist / 1000:.3f}",
            "geometry":     geometry,
        })

    # ── 4. Sort, apply mode ──────────────────────────────────────────────────
    results.sort(key=lambda x: x["road_dist_m"])
    return results[:1] if mode == "shortest" else results
