//! Run pipeline modal: target input, network y/n, then "started" message.

use crate::app::{RunPipelineState, RunPipelineStep};
use ratatui::prelude::*;
use ratatui::widgets::*;

pub fn draw(frame: &mut Frame, state: &RunPipelineState, area: Rect) {
    let width = 52.min(area.width.saturating_sub(4));
    let height = 10.min(area.height.saturating_sub(4));
    let x = area.x + (area.width.saturating_sub(width)) / 2;
    let y = area.y + (area.height.saturating_sub(height)) / 2;
    let block_area = Rect {
        x,
        y,
        width,
        height,
    };
    let block = Block::default()
        .title(" Run pipeline ")
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .style(Style::default().bg(Color::Black).fg(Color::White));
    let inner = block.inner(block_area);
    frame.render_widget(block, block_area);

    let mut lines = vec![];

    match &state.step {
        RunPipelineStep::TargetInput => {
            lines.push(Line::from("Target (Twitter username):").style(Style::default().fg(Color::Cyan)));
            lines.push(Line::from(""));
            let input = if state.target.is_empty() {
                "_".to_string()
            } else {
                state.target.clone()
            };
            lines.push(Line::from(format!("  {}", input)));
            lines.push(Line::from(""));
            lines.push(Line::from("  Enter = next   Esc = cancel"));
        }
        RunPipelineStep::NetworkConfirm => {
            lines.push(Line::from("Run network profiling? (graph + key nodes)").style(Style::default().fg(Color::Cyan)));
            lines.push(Line::from(""));
            lines.push(Line::from("  [y] Yes   [n] No   Esc = cancel"));
        }
        RunPipelineStep::Started(msg) => {
            for part in msg.split('\n') {
                lines.push(Line::from(part));
            }
            lines.push(Line::from(""));
            lines.push(Line::from("  Esc = close"));
        }
    }

    let paragraph = Paragraph::new(lines).wrap(Wrap { trim: true });
    frame.render_widget(paragraph, inner);
}
