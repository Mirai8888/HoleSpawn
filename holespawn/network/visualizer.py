"""
Generate a standalone HTML file (network_graph.html) with D3.js force-directed graph.
Nodes colored by community, size by centrality; edges by weight; tooltips and filters.
"""

import json
import random
from pathlib import Path
from typing import Any

from .graph_analysis import NetworkAnalysis, network_analysis_to_dict

# Cap nodes for viz so layout is tractable and HTML doesn't blow up (avoids black screen / freeze)
MAX_VIZ_NODES = 450


def generate_network_graph_html(
    analysis: NetworkAnalysis,
    node_profiles: dict[str, dict[str, Any]],
    output_path: Path | str,
    target_username: str = "",
) -> None:
    """
    Write a self-contained HTML file with D3.js force-directed graph.
    Nodes: color by community, size by centrality; tooltips; click for profile summary.
    For large graphs, subsamples to MAX_VIZ_NODES so the viz renders (avoids black screen).
    """
    output_path = Path(output_path)
    data = network_analysis_to_dict(analysis)
    nodes = data["nodes"]
    edges = data["edges"]
    node_community = data.get("node_community") or {}
    betweenness = data.get("betweenness") or {}
    bridge_usernames = {b["username"] for b in data.get("bridge_nodes", [])[:30]}
    vulnerable_usernames = {v["username"] for v in data.get("vulnerable_entry_points", [])[:30]}
    bet_vals = list(betweenness.values()) or [0]
    bet_max = max(bet_vals) or 1

    # Subsample for large graphs so D3 layout works and HTML is small
    if len(nodes) > MAX_VIZ_NODES:
        priority = set()
        if target_username:
            priority.add(target_username)
        priority.update(bridge_usernames, vulnerable_usernames)
        priority.update(a["username"] for a in data.get("amplifiers", [])[:15])
        rest = [n for n in nodes if n not in priority]
        random.shuffle(rest)
        keep = list(priority) + rest[: MAX_VIZ_NODES - len(priority)]
        nodes = [n for n in nodes if n in keep]
        edge_set = {(e["source"], e["target"]) for e in edges}
        edges = [e for e in edges if e["source"] in keep and e["target"] in keep]

    node_data = []
    for n in nodes:
        cid = node_community.get(n, 0)
        bet = betweenness.get(n, 0)
        radius = 0.3 + 0.9 * (bet / bet_max) if bet_max else 0.5
        role = "bridge" if n in bridge_usernames else ("entry" if n in vulnerable_usernames else "node")
        prof = node_profiles.get(n, {})
        score = prof.get("strategic_value_score")
        tooltip = f"@{n} | Community {cid} | {role}"
        if score is not None:
            tooltip += f" | Value {score}/10"
        profile_summary = (prof.get("profile_summary") or "")[:300]
        approach = json.dumps(prof.get("approach_vectors") or [])[:200]
        node_data.append({
            "id": n,
            "community": cid,
            "radius": round(radius, 2),
            "role": role,
            "betweenness": round(bet, 4),
            "tooltip": tooltip,
            "profile_summary": profile_summary,
            "approach": approach,
        })
    edge_data = [{"source": e["source"], "target": e["target"], "weight": max(0.1, min(3, e.get("weight", 1)))} for e in edges]

    # Embed data in script type=application/json to avoid quote/escape issues (was causing black screen)
    nodes_json_embed = json.dumps(node_data)
    edges_json_embed = json.dumps(edge_data)
    target_esc = target_username.replace("\\", "\\\\").replace("'", "\\'").replace("<", "").replace(">", "")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Network graph – {target_esc}</title>
  <script src="https://d3js.org/d3.v7.min.js"></script>
  <style>
    body {{ margin: 0; font-family: system-ui, sans-serif; background: #1a1a2e; color: #e0e0e0; }}
    #chart {{ position: absolute; left: 0; top: 0; width: 100vw; height: 100vh; }}
    .node {{ cursor: pointer; stroke: #fff; stroke-width: 1px; }}
    .node.bridge {{ stroke: #f59e0b; stroke-width: 2px; }}
    .node.entry {{ stroke: #10b981; stroke-width: 2px; }}
    .link {{ stroke: #4a5568; stroke-opacity: 0.4; }}
    #tooltip {{ position: absolute; padding: 8px 12px; background: rgba(0,0,0,0.9); border-radius: 6px; font-size: 12px; max-width: 320px; pointer-events: none; z-index: 10; border: 1px solid #333; }}
    #detail {{ position: fixed; bottom: 0; left: 0; right: 0; max-height: 200px; padding: 12px; background: rgba(0,0,0,0.95); overflow-y: auto; font-size: 13px; }}
    #filters {{ position: absolute; top: 10px; left: 10px; padding: 10px; background: rgba(0,0,0,0.8); border-radius: 8px; font-size: 12px; z-index: 5; }}
    #filters label {{ display: block; margin: 4px 0; cursor: pointer; }}
  </style>
</head>
<body>
  <div id="filters">
    <strong>Filter by community</strong>
    <div id="community-checkboxes"></div>
    <label><input type="checkbox" id="show-bridges" checked> Highlight bridges</label>
    <label><input type="checkbox" id="show-entry" checked> Highlight entry points</label>
  </div>
  <div id="tooltip"></div>
  <div id="detail"></div>
  <div id="chart"></div>
  <script type="application/json" id="nodes-data">{nodes_json_embed}</script>
  <script type="application/json" id="edges-data">{edges_json_embed}</script>
  <script>
    const nodeData = JSON.parse(document.getElementById('nodes-data').textContent);
    const edgeData = JSON.parse(document.getElementById('edges-data').textContent);
    const targetUsername = '{target_esc}';

    const width = window.innerWidth || 960;
    const height = window.innerHeight || 600;
    const svg = d3.select('#chart').append('svg').attr('width', width).attr('height', height).style('background-color', '#0a0a0a');
    const g = svg.append('g');

    const color = d3.scaleOrdinal(d3.schemeCategory10);
    const communities = [...new Set(nodeData.map(d => d.community))];
    const communityCheckboxes = d3.select('#community-checkboxes');
    communities.forEach(c => {{
      communityCheckboxes.append('label').attr('class', 'filter-cb').html('<input type="checkbox" class="community-filter" value="' + c + '" checked> Community ' + c + ' ');
    }});

    const link = g.append('g').attr('class', 'links').selectAll('line').data(edgeData).join('line').attr('class', 'link').attr('stroke-width', d => Math.sqrt(d.weight));
    const node = g.append('g').attr('class', 'nodes').selectAll('circle').data(nodeData).join('circle').attr('class', d => 'node ' + d.role).attr('r', d => Math.max(2, 3 + d.radius * 5)).attr('fill', d => color(d.community)).on('mouseover', function(ev, d) {{
      d3.select('#tooltip').style('display', 'block').style('left', (ev.pageX + 10) + 'px').style('top', (ev.pageY + 10) + 'px').html(d.tooltip + '<br><small>' + (d.profile_summary || '') + '</small>');
    }}).on('mouseout', () => {{ d3.select('#tooltip').style('display', 'none'); }}).on('click', function(ev, d) {{
      const esc = (s) => (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
      d3.select('#detail').html('<strong>@' + esc(d.id) + '</strong> (Community ' + d.community + ', ' + d.role + ')<br>' + (d.profile_summary ? '<p>' + esc(d.profile_summary) + '</p>' : '') + (d.approach ? '<p>Approach: ' + esc(d.approach) + '</p>' : ''));
    }});

    const simulation = d3.forceSimulation(nodeData).force('link', d3.forceLink(edgeData).id(d => d.id).distance(80).strength(0.2)).force('charge', d3.forceManyBody().strength(-200)).force('center', d3.forceCenter(width/2, height/2)).force('collision', d3.forceCollide().radius(d => (d.radius || 0.5) * 5 + 2)).on('tick', () => {{
      link.attr('x1', d => d.source.x).attr('y1', d => d.source.y).attr('x2', d => d.target.x).attr('y2', d => d.target.y);
      node.attr('cx', d => d.x).attr('cy', d => d.y);
    }});

    d3.selectAll('.community-filter').on('change', function() {{
      const checked = new Set([...d3.selectAll('.community-filter:checked')].map(el => el.value));
      node.style('display', d => checked.has(String(d.community)) ? 'block' : 'none');
    }});
    d3.select('#show-bridges').on('change', function() {{ node.classed('bridge', d => d.role === 'bridge' && this.checked); }});
    d3.select('#show-entry').on('change', function() {{ node.classed('entry', d => d.role === 'entry' && this.checked); }});
  </script>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
