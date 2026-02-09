//! Live build monitor: infer pipeline stages from files in output dir; show cost from cost_breakdown.json.

use crate::app::App;
use ratatui::prelude::*;
use ratatui::widgets::*;
use std::path::Path;

fn stage_status(path: &Path, file: &str) -> &'static str {
    if path.join(file).exists() {
        "✓"
    } else {
        "—"
    }
}

#[derive(serde::Deserialize)]
struct CostBreakdown {
    #[serde(default)]
    total_cost: f64,
    #[serde(default)]
    total_input_tokens: u64,
    #[serde(default)]
    total_output_tokens: u64,
    #[serde(default)]
    calls: Vec<CostCall>,
}

#[derive(serde::Deserialize)]
struct CostCall {
    #[serde(default)]
    operation: String,
    #[serde(default)]
    input: u64,
    #[serde(default)]
    output: u64,
    #[serde(default)]
    timestamp: String,
}

pub fn draw(frame: &mut Frame, app: &App, area: Rect) {
    let margin = Margin::new(1, 1);
    let block = Block::default()
        .title(" Live Build Monitor ")
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded);
    frame.render_widget(&block, area);
    let inner = block.inner(area).inner(&margin);

    let path = app
        .live_path
        .as_deref()
        .or_else(|| app.selected_profile().map(|p| p.path.as_path()))
        .unwrap_or(Path::new("."));

    let mut lines: Vec<Line> = vec![
        Line::from(format!("Watching: {}", path.display())),
        Line::from(""),
        Line::from("Pipeline stages (from file presence):").style(Style::default().fg(Color::Cyan)),
        Line::from(format!("  behavioral_matrix.json  {}", stage_status(path, "behavioral_matrix.json"))),
        Line::from(format!("  binding_protocol.md     {}", stage_status(path, "binding_protocol.md"))),
        Line::from(format!("  trap_architecture/      {}", stage_status(path, "trap_architecture"))),
        Line::from(format!("  network_analysis.json   {}", stage_status(path, "network_analysis.json"))),
        Line::from(format!("  network_report.md       {}", stage_status(path, "network_report.md"))),
        Line::from(""),
    ];

    let cost_path = path.join("cost_breakdown.json");
    if cost_path.exists() {
        if let Ok(s) = std::fs::read_to_string(&cost_path) {
            if let Ok(cost) = serde_json::from_str::<CostBreakdown>(&s) {
                lines.push(Line::from("Cost (cost_breakdown.json):").style(Style::default().fg(Color::Cyan)));
                lines.push(Line::from(format!("  Total: ${:.6}", cost.total_cost)));
                lines.push(Line::from(format!("  Input tokens: {}  Output: {}", cost.total_input_tokens, cost.total_output_tokens)));
                if !cost.calls.is_empty() {
                    lines.push(Line::from("  Calls:"));
                    for c in cost.calls.iter().take(5) {
                        lines.push(Line::from(format!("    {}  in:{} out:{}  {}", c.operation, c.input, c.output, c.timestamp)));
                    }
                }
                lines.push(Line::from(""));
            }
        }
    } else {
        lines.push(Line::from("(No cost_breakdown.json)"));
    }

    lines.push(Line::from(""));
    lines.push(Line::from("[Esc] Back — Point output dir via CLI or select a profile with data."));

    let paragraph = Paragraph::new(lines).wrap(Wrap { trim: true });
    frame.render_widget(paragraph, inner);
}
