"""CK3 mod knowledge-map generator.

Scans a mod folder, discovers all entities (traits, perks, events, …),
finds cross-references between them, and renders an interactive HTML
force-directed graph grouped by entity type using NetworkX + pyvis.
"""
import math
import pathlib
import re
from dataclasses import dataclass, field
from typing import Optional

import networkx as nx

# ── Entity type metadata ──────────────────────────────────────────────────
# (pyvis group id, node color, legend label)
_TYPE_META: dict[str, tuple[int, str, str]] = {
    "trait":       (1, "#4a9fd4", "Trait"),
    "perk":        (2, "#5cb85c", "Perk"),
    "building":    (3, "#c9a227", "Building"),
    "artifact":    (4, "#e8a838", "Artifact"),
    "decision":    (5, "#9b59b6", "Decision"),
    "event":       (6, "#e74c3c", "Event"),
    "interaction": (7, "#e67e22", "Interaction"),
    "religion":    (8, "#f1d010", "Religion"),
    "culture":     (9, "#1abc9c", "Culture"),
}

# ── Folders to scan for each entity type ─────────────────────────────────
_FOLDER_MAP: list[tuple[str, str]] = [
    ("common/traits",                 "trait"),
    ("common/lifestyle_perks",        "perk"),
    ("common/buildings",              "building"),
    ("common/artifacts/templates",    "artifact"),
    ("common/decisions",              "decision"),
    ("common/character_interactions", "interaction"),
    ("common/religion/religions",     "religion"),
    ("common/culture/cultures",       "culture"),
]

# ── Regex patterns ────────────────────────────────────────────────────────
_TOP_BLOCK_RE     = re.compile(r'^([a-z][a-z0-9_]*)\s*=\s*\{', re.MULTILINE)
_NAMESPACE_RE     = re.compile(r'^\s*namespace\s*=\s*([a-z0-9_]+)', re.MULTILINE)
_EVENT_NUM_RE     = re.compile(r'^([a-z0-9_]+\.\d+|\d+)\s*=\s*\{', re.MULTILINE)
_PARENT_RE        = re.compile(r'\bparent\s*=\s*([a-z0-9_]+)')
_HAS_TRAIT_RE     = re.compile(r'\bhas_trait\s*=\s*([a-z0-9_]+)')
_ADD_TRAIT_RE     = re.compile(r'\b(?:add_trait|remove_trait)\s*=\s*([a-z0-9_]+)')
_NEXT_BUILDING_RE = re.compile(r'\bnext_building\s*=\s*([a-z0-9_]+)')
_OPPOSITES_RE     = re.compile(r'\bopposites\s*=\s*\{([^}]+)\}')
_TRIGGER_EVENT_RE = re.compile(
    r'\btrigger_event\s*=\s*\{\s*id\s*=\s*([a-z0-9_.]+)'
    r'|\btrigger_event\s*=\s*([a-z0-9_.]+)'
)


@dataclass
class _NodeInfo:
    entity_type: str
    source_file: str


@dataclass
class _EdgeInfo:
    src: str
    dst: str
    label: str


def _read(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


def _split_blocks(text: str) -> list[tuple[str, str]]:
    """Return [(block_id, block_text)] for every top-level `id = {` in text."""
    matches = list(_TOP_BLOCK_RE.finditer(text))
    blocks = []
    for i, m in enumerate(matches):
        block_id = m.group(1)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        blocks.append((block_id, text[start:end]))
    return blocks


def _event_blocks(text: str) -> list[tuple[str, str]]:
    """Return [(event_id, block_text)] for a CK3 events file."""
    ns_match = _NAMESPACE_RE.search(text)
    ns = ns_match.group(1) if ns_match else ""
    matches = list(_EVENT_NUM_RE.finditer(text))
    blocks = []
    for i, m in enumerate(matches):
        raw_id = m.group(1)
        # If raw_id is purely numeric, prefix with namespace
        event_id = raw_id if "." in raw_id else (f"{ns}.{raw_id}" if ns else raw_id)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        blocks.append((event_id, text[start:end]))
    return blocks


def _discover_nodes(mod_root: pathlib.Path) -> dict[str, _NodeInfo]:
    nodes: dict[str, _NodeInfo] = {}

    for rel_path, entity_type in _FOLDER_MAP:
        folder = mod_root / rel_path
        if not folder.is_dir():
            continue
        for txt_file in sorted(folder.rglob("*.txt")):
            text = _read(txt_file)
            rel = str(txt_file.relative_to(mod_root))
            for block_id, _ in _split_blocks(text):
                if block_id not in nodes:
                    nodes[block_id] = _NodeInfo(entity_type, rel)

    # Events have namespace-prefixed IDs
    events_dir = mod_root / "events"
    if events_dir.is_dir():
        for txt_file in sorted(events_dir.rglob("*.txt")):
            text = _read(txt_file)
            rel = str(txt_file.relative_to(mod_root))
            for event_id, _ in _event_blocks(text):
                if event_id not in nodes:
                    nodes[event_id] = _NodeInfo("event", rel)

    return nodes


def _discover_edges(
    mod_root: pathlib.Path, nodes: dict[str, _NodeInfo]
) -> list[_EdgeInfo]:
    edges: list[_EdgeInfo] = []
    known = set(nodes.keys())

    def _add(src: str, dst: str, label: str) -> None:
        if src in known and dst in known and src != dst:
            edges.append(_EdgeInfo(src, dst, label))

    # ── Perks ─────────────────────────────────────────────────────────────
    perk_dir = mod_root / "common" / "lifestyle_perks"
    if perk_dir.is_dir():
        for txt_file in perk_dir.rglob("*.txt"):
            text = _read(txt_file)
            for perk_id, block in _split_blocks(text):
                for m in _PARENT_RE.finditer(block):
                    _add(perk_id, m.group(1), "parent")
                for m in _HAS_TRAIT_RE.finditer(block):
                    _add(perk_id, m.group(1), "requires trait")

    # ── Traits ────────────────────────────────────────────────────────────
    trait_dir = mod_root / "common" / "traits"
    if trait_dir.is_dir():
        for txt_file in trait_dir.rglob("*.txt"):
            text = _read(txt_file)
            for trait_id, block in _split_blocks(text):
                for m in _OPPOSITES_RE.finditer(block):
                    for opp in m.group(1).split():
                        _add(trait_id, opp.strip(), "opposes")

    # ── Buildings ─────────────────────────────────────────────────────────
    bld_dir = mod_root / "common" / "buildings"
    if bld_dir.is_dir():
        for txt_file in bld_dir.rglob("*.txt"):
            text = _read(txt_file)
            for bld_id, block in _split_blocks(text):
                for m in _NEXT_BUILDING_RE.finditer(block):
                    _add(bld_id, m.group(1), "upgrades to")

    # ── Decisions ─────────────────────────────────────────────────────────
    dec_dir = mod_root / "common" / "decisions"
    if dec_dir.is_dir():
        for txt_file in dec_dir.rglob("*.txt"):
            text = _read(txt_file)
            for dec_id, block in _split_blocks(text):
                for m in _HAS_TRAIT_RE.finditer(block):
                    _add(dec_id, m.group(1), "checks trait")
                for m in _ADD_TRAIT_RE.finditer(block):
                    _add(dec_id, m.group(1), "modifies trait")
                for m in _TRIGGER_EVENT_RE.finditer(block):
                    eid = m.group(1) or m.group(2)
                    if eid:
                        _add(dec_id, eid, "triggers")

    # ── Character interactions ────────────────────────────────────────────
    int_dir = mod_root / "common" / "character_interactions"
    if int_dir.is_dir():
        for txt_file in int_dir.rglob("*.txt"):
            text = _read(txt_file)
            for int_id, block in _split_blocks(text):
                for m in _HAS_TRAIT_RE.finditer(block):
                    _add(int_id, m.group(1), "checks trait")
                for m in _TRIGGER_EVENT_RE.finditer(block):
                    eid = m.group(1) or m.group(2)
                    if eid:
                        _add(int_id, eid, "triggers")

    # ── Events ────────────────────────────────────────────────────────────
    events_dir = mod_root / "events"
    if events_dir.is_dir():
        for txt_file in events_dir.rglob("*.txt"):
            text = _read(txt_file)
            ns_match = _NAMESPACE_RE.search(text)
            ns = ns_match.group(1) if ns_match else ""
            for raw_id, block in _event_blocks(text):
                ev_id = raw_id if "." in raw_id else (f"{ns}.{raw_id}" if ns else raw_id)
                for m in _ADD_TRAIT_RE.finditer(block):
                    _add(ev_id, m.group(1), "adds/removes trait")
                for m in _HAS_TRAIT_RE.finditer(block):
                    _add(ev_id, m.group(1), "checks trait")
                for m in _TRIGGER_EVENT_RE.finditer(block):
                    eid = m.group(1) or m.group(2)
                    if eid:
                        _add(ev_id, eid, "triggers")

    return edges


def build_graph(mod_root: pathlib.Path) -> tuple[nx.DiGraph, dict[str, _NodeInfo]]:
    """Build and return the NetworkX graph + node metadata for a mod folder."""
    nodes = _discover_nodes(mod_root)
    edges = _discover_edges(mod_root, nodes)

    G = nx.DiGraph()
    for node_id, info in nodes.items():
        G.add_node(node_id, entity_type=info.entity_type, source_file=info.source_file)
    for e in edges:
        G.add_edge(e.src, e.dst, label=e.label)

    return G, nodes


def _type_initial_positions(
    nodes: dict[str, _NodeInfo], radius: float = 1100
) -> dict[str, tuple[float, float]]:
    """Assign each node a starting (x, y) inside its type's sector of a circle."""
    # Collect nodes per type, preserving _TYPE_META order
    buckets: dict[str, list[str]] = {t: [] for t in _TYPE_META}
    for node_id, info in nodes.items():
        buckets.setdefault(info.entity_type, []).append(node_id)

    active_types = [t for t in buckets if buckets[t]]
    n_types = len(active_types)
    positions: dict[str, tuple[float, float]] = {}

    for i, t in enumerate(active_types):
        cluster_angle = 2 * math.pi * i / n_types
        cx = radius * math.cos(cluster_angle)
        cy = radius * math.sin(cluster_angle)
        members = buckets[t]
        spread = 90 * math.sqrt(len(members))  # widen spread for large clusters
        for j, node_id in enumerate(members):
            sub_angle = 2 * math.pi * j / max(len(members), 1)
            positions[node_id] = (
                cx + spread * math.cos(sub_angle),
                cy + spread * math.sin(sub_angle),
            )
    return positions


def render_to_html(
    G: nx.DiGraph,
    nodes: dict[str, _NodeInfo],
    output_path: pathlib.Path,
    mod_name: str = "",
) -> None:
    """Render the graph to an interactive pyvis HTML file."""
    from pyvis.network import Network

    net = Network(
        height="900px",
        width="100%",
        bgcolor="#1a1a2e",
        font_color="#e0e0e0",
        directed=True,
        notebook=False,
    )
    net.barnes_hut(spring_length=200, spring_strength=0.03, damping=0.09)

    initial_pos = _type_initial_positions(nodes)

    for node_id, info in nodes.items():
        group, color, type_label = _TYPE_META.get(
            info.entity_type, (0, "#888888", info.entity_type)
        )
        x, y = initial_pos.get(node_id, (0.0, 0.0))
        net.add_node(
            node_id,
            label=node_id,
            title=f"<b>{node_id}</b><br>Type: {type_label}<br>File: {info.source_file}",
            color=color,
            group=group,
            shape="dot",
            size=16,
            x=x,
            y=y,
        )

    # Add a hidden hub node per type so same-type nodes stay attracted during physics
    buckets: dict[str, list[str]] = {}
    for node_id, info in nodes.items():
        buckets.setdefault(info.entity_type, []).append(node_id)
    for t, members in buckets.items():
        if len(members) < 2:
            continue
        hub_id = f"__hub_{t}__"
        # Hub sits at the centroid of the sector so physics starts it in the right place
        xs = [initial_pos[m][0] for m in members]
        ys = [initial_pos[m][1] for m in members]
        net.add_node(
            hub_id,
            label="",
            size=0,
            color="rgba(0,0,0,0)",
            hidden=True,
            x=sum(xs) / len(xs),
            y=sum(ys) / len(ys),
            physics=True,
        )
        for member in members:
            # Hidden spring edges pull cluster members toward the hub
            net.add_edge(
                hub_id, member,
                hidden=True,
                physics=True,
                length=150,
                color="rgba(0,0,0,0)",
                width=0,
            )

    for src, dst, data in G.edges(data=True):
        net.add_edge(src, dst, title=data.get("label", ""), label=data.get("label", ""))

    # Inject a legend and title into the generated HTML
    legend_html = _build_legend_html(mod_name)
    net.set_options(_PYVIS_OPTIONS)
    html = net.generate_html()
    html = html.replace("</body>", legend_html + "\n</body>", 1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def _build_legend_html(mod_name: str) -> str:
    items = "".join(
        f'<div style="display:flex;align-items:center;gap:8px;margin:4px 0">'
        f'<div style="width:14px;height:14px;border-radius:50%;background:{color}"></div>'
        f'<span>{label}</span></div>'
        for _, color, label in _TYPE_META.values()
    )
    title_text = f"Knowledge Map — {mod_name}" if mod_name else "Knowledge Map"
    return f"""
<div style="position:fixed;top:12px;left:12px;background:#0d0d1a;
            border:1px solid #333;border-radius:8px;padding:12px 16px;
            font-family:sans-serif;font-size:13px;color:#ddd;z-index:9999">
  <div style="font-weight:bold;margin-bottom:8px;color:#fff">{title_text}</div>
  {items}
</div>"""


_PYVIS_OPTIONS = """{
  "edges": {
    "arrows": { "to": { "enabled": true, "scaleFactor": 0.6 } },
    "color": { "color": "#556677", "highlight": "#88aacc" },
    "font": { "size": 10, "color": "#aabbcc", "strokeWidth": 0 },
    "smooth": { "type": "curvedCW", "roundness": 0.2 }
  },
  "nodes": {
    "borderWidth": 1,
    "borderWidthSelected": 3,
    "font": { "size": 13, "color": "#e0e0e0" }
  },
  "physics": {
    "barnesHut": {
      "gravitationalConstant": -14000,
      "centralGravity": 0.05,
      "springLength": 200,
      "springConstant": 0.03,
      "damping": 0.09
    },
    "minVelocity": 0.75
  },
  "interaction": {
    "hover": true,
    "tooltipDelay": 150,
    "navigationButtons": true,
    "keyboard": true
  }
}"""


def register(mcp, repo_root: pathlib.Path):
    @mcp.tool()
    def generate_knowledge_map(
        mod_name: str,
        open_browser: bool = False,
    ) -> str:
        """Generate an interactive HTML knowledge map of a mod's files and relationships.

        Scans the mod folder for traits, perks, buildings, artifacts, decisions,
        events, interactions, religions, and cultures. Draws edges between entities
        that reference each other (e.g. a perk that requires a trait, an event that
        adds a trait, a decision that triggers an event). Renders to a self-contained
        interactive HTML file you can open in any browser.

        Args:
            mod_name: Mod folder name inside the repo root (e.g. 'WizardMod').
            open_browser: If True, open the map in the default browser after generation.
        Returns:
            Path to the generated HTML file and a short summary of what was found.
        """
        mod_root = repo_root / mod_name
        if not mod_root.is_dir():
            return f"Error: mod folder not found: {mod_root}"

        G, nodes = build_graph(mod_root)

        out_dir = repo_root / mod_name / "knowledge_map"
        out_path = out_dir / f"{mod_name}_knowledge_map.html"
        render_to_html(G, nodes, out_path, mod_name=mod_name)

        type_counts: dict[str, int] = {}
        for info in nodes.values():
            type_counts[info.entity_type] = type_counts.get(info.entity_type, 0) + 1

        summary_lines = [f"{v} {k}(s)" for k, v in sorted(type_counts.items())]
        edge_count = G.number_of_edges()

        if open_browser:
            import webbrowser
            webbrowser.open(out_path.as_uri())

        return (
            f"Knowledge map generated: {out_path}\n"
            f"Entities: {', '.join(summary_lines)}\n"
            f"Relationships: {edge_count} edges"
        )


# ── LangChain tool factory ─────────────────────────────────────────────────

class _ToolCollector:
    """Mimics FastMCP so register() populates tools without a real server."""
    def __init__(self):
        self._fns: list = []
    def tool(self, **_):
        def _wrap(fn):
            self._fns.append(fn)
            return fn
        return _wrap


def get_tools(repo_root: pathlib.Path) -> list:
    """Return this module's tools as LangChain StructuredTool objects."""
    from langchain_core.tools import StructuredTool
    collector = _ToolCollector()
    register(collector, repo_root)
    return [StructuredTool.from_function(fn) for fn in collector._fns]
