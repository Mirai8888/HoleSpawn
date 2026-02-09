//! ASCII graph view: nodes and edges from NetworkAnalysis (list + simple 2D layout).

use crate::app::App;
use crate::types::NetworkEdge;
use ratatui::prelude::*;
use ratatui::widgets::*;
use std::collections::HashMap;

/// Simple force-directed-ish positions: map node index -> (x, y) in 0..1.
fn layout_nodes(nodes: &[String], edges: &[NetworkEdge], _width: u16, _height: u16) -> HashMap<usize, (f64, f64)> {
    let n = nodes.len();
    let mut pos: HashMap<usize, (f64, f64)> = (0..n)
        .map(|i| {
            let t = i as f64 / (n as f64 + 1.0);
            (i, (t * 0.8 + 0.1, 0.5))
        })
        .collect();
    let idx: HashMap<&str, usize> = nodes.iter().enumerate().map(|(i, s)| (s.as_str(), i)).collect();
    for _ in 0..20 {
        let mut force_x = vec![0.0; n];
        let mut force_y = vec![0.0; n];
        for e in edges {
            let i = idx.get(e.source.as_str());
            let j = idx.get(e.target.as_str());
            if let (Some(&i), Some(&j)) = (i, j) {
                let (xi, yi) = pos.get(&i).copied().unwrap_or((0.5, 0.5));
                let (xj, yj) = pos.get(&j).copied().unwrap_or((0.5, 0.5));
                let dx = xj - xi;
                let dy = yj - yi;
                let d = (dx * dx + dy * dy).sqrt().max(0.01);
                let f = (d - 0.15).min(0.1);
                let ux = dx / d;
                let uy = dy / d;
                force_x[i] += ux * f;
                force_y[i] += uy * f;
                force_x[j] -= ux * f;
                force_y[j] -= uy * f;
            }
        }
        for i in 0..n {
            if let Some(p) = pos.get_mut(&i) {
                p.0 = (p.0 + force_x[i] * 0.3).clamp(0.0, 1.0);
                p.1 = (p.1 + force_y[i] * 0.3).clamp(0.0, 1.0);
            }
        }
    }
    pos
}

pub fn draw(frame: &mut Frame, app: &App, area: Rect) {
    let margin = Margin::new(1, 1);
    let block = Block::default()
        .title(" Network Graph ")
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded);
    let inner = block.inner(area).inner(&margin);
    frame.render_widget(&block, area);
    let (graph_w, graph_h) = (inner.width.saturating_sub(2) as usize, inner.height.saturating_sub(2) as usize);
    if graph_w == 0 || graph_h == 0 {
        return;
    }

    if let Some(net) = &app.network {
        let nodes = &net.nodes;
        let edges = &net.edges;
        let n = nodes.len();
        if n == 0 {
            let p = Paragraph::new("No nodes.").wrap(Wrap { trim: true });
            frame.render_widget(p, inner);
            return;
        }

        let pos = layout_nodes(nodes, edges, inner.width, inner.height);
        let mut canvas = vec![vec![b' '; graph_w]; graph_h];
        let node_to_char = |i: usize| -> u8 {
            if Some(i) == app.selected_node_index {
                b'@'
            } else {
                b'*'
            }
        };
        for (i, (x, y)) in &pos {
            let cx = (x * (graph_w as f64 - 1.0).max(0.0)) as usize;
            let cy = (y * (graph_h as f64 - 1.0).max(0.0)) as usize;
            if cy < graph_h && cx < graph_w {
                canvas[cy][cx] = node_to_char(*i);
            }
        }
        for e in edges.iter().take(500) {
            let i = net.nodes.iter().position(|s| s == &e.source);
            let j = net.nodes.iter().position(|s| s == &e.target);
            if let (Some(i), Some(j)) = (i, j) {
                let (x0, y0) = pos.get(&i).copied().unwrap_or((0.5, 0.5));
                let (x1, y1) = pos.get(&j).copied().unwrap_or((0.5, 0.5));
                let cx0 = (x0 * (graph_w as f64 - 1.0)) as i32;
                let cy0 = (y0 * (graph_h as f64 - 1.0)) as i32;
                let cx1 = (x1 * (graph_w as f64 - 1.0)) as i32;
                let cy1 = (y1 * (graph_h as f64 - 1.0)) as i32;
                let steps = (cx1 - cx0).abs().max((cy1 - cy0).abs()).max(1) as usize;
                for t in 0..=steps {
                    let t = t as f64 / steps as f64;
                    let x = x0 + t * (x1 - x0);
                    let y = y0 + t * (y1 - y0);
                    let px = (x * (graph_w as f64 - 1.0)) as usize;
                    let py = (y * (graph_h as f64 - 1.0)) as usize;
                    if py < graph_h && px < graph_w && canvas[py][px] == b' ' {
                        canvas[py][px] = b'.';
                    }
                }
            }
        }
        let lines: Vec<Line> = canvas
            .iter()
            .map(|row| Line::from(String::from_utf8_lossy(row).into_owned()))
            .collect();
        let paragraph = Paragraph::new(lines);
        frame.render_widget(paragraph, inner);

        let sel = app.selected_node_index.unwrap_or(0);
        let name = nodes.get(sel).map(|s| s.as_str()).unwrap_or("—");
        let hint = format!(" j/k: node  Enter: detail  [r] report  Esc: back — {}", name);
        let hint_area = Rect {
            x: inner.x,
            y: inner.y + inner.height.saturating_sub(1),
            width: inner.width,
            height: 1,
        };
        frame.render_widget(Paragraph::new(hint), hint_area);
    } else {
        let p = Paragraph::new("No network loaded.").wrap(Wrap { trim: true });
        frame.render_widget(p, inner);
    }
}
