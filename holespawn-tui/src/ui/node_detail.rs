//! Node detail view: one node's role, degree, betweenness, strategic value, etc.

use crate::app::App;
use ratatui::prelude::*;
use ratatui::widgets::*;

pub fn draw(frame: &mut Frame, app: &App, area: Rect) {
    let margin = Margin::new(1, 1);
    let block = Block::default()
        .title(" Node Detail ")
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded);
    frame.render_widget(&block, area);
    let inner = block.inner(area).inner(&margin);

    let mut lines: Vec<Line> = vec![];
    if let (Some(net), Some(idx)) = (&app.network, app.selected_node_index) {
        let name = net.nodes.get(idx).map(|s| s.as_str()).unwrap_or("—");
        lines.push(Line::from(format!("Node: {}", name)).style(Style::default().fg(Color::Cyan)));
        lines.push(Line::from(""));

        if let Some(metrics) = net.node_metrics.get(name) {
            lines.push(Line::from("Metrics:"));
            lines.push(Line::from(format!("  degree: {}  in: {}  out: {}", metrics.degree, metrics.in_degree, metrics.out_degree)));
            lines.push(Line::from(format!("  betweenness: {:.4}  community: {}", metrics.betweenness, metrics.community)));
            if !metrics.role.is_empty() {
                lines.push(Line::from(format!("  role: {}", metrics.role)));
            }
            if let Some(e) = metrics.eigenvector {
                lines.push(Line::from(format!("  eigenvector: {:.4}", e)));
            }
            lines.push(Line::from(""));
        }
        let betweenness = net.betweenness.get(name).copied().unwrap_or(0.0);
        if betweenness > 0.0 {
            lines.push(Line::from(format!("Betweenness (global): {:.4}", betweenness)));
            lines.push(Line::from(""));
        }
        let in_d = net.in_degree.get(name).copied().unwrap_or(0);
        let out_d = net.out_degree.get(name).copied().unwrap_or(0);
        if in_d > 0 || out_d > 0 {
            lines.push(Line::from(format!("In-degree: {}  Out-degree: {}", in_d, out_d)));
            lines.push(Line::from(""));
        }

        if net.bridge_nodes.iter().any(|b| b.username == name) {
            lines.push(Line::from("Bridge node (connects communities)").style(Style::default().fg(Color::Yellow)));
        }
        if net.gatekeepers.iter().any(|g| g.username == name) {
            lines.push(Line::from("Gatekeeper").style(Style::default().fg(Color::Yellow)));
        }
        if let Some(v) = net.vulnerable_entry_points.iter().find(|v| v.username == name) {
            lines.push(Line::from("Vulnerable entry point").style(Style::default().fg(Color::Red)));
            if !v.reason.is_empty() {
                lines.push(Line::from(format!("  reason: {}", v.reason)));
            }
        }

        lines.push(Line::from(""));
        lines.push(Line::from("[Esc] Back"));
    } else {
        lines.push(Line::from("No node selected."));
    }

    let paragraph = Paragraph::new(lines)
        .scroll((app.scroll, 0))
        .wrap(Wrap { trim: true });
    frame.render_widget(paragraph, inner);
}
