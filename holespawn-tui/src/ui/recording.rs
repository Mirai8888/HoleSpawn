//! Recording tab: list of subjects from recordings.db (last snapshot, count). Data from Python temporal --list-subjects.

use crate::app::App;
use ratatui::prelude::*;
use ratatui::widgets::*;

pub fn draw(frame: &mut Frame, app: &App, area: Rect) {
    let margin = Margin::new(1, 1);
    let block = Block::default()
        .title(" Recording — watched subjects ")
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded);
    frame.render_widget(&block, area);
    let inner = block.inner(area).inner(&margin);

    let summary = app.recordings_summary.as_ref();
    let mut lines: Vec<Line> = vec![
        Line::from("Data from recordings/ (recordings.db). Refreshed when you open this tab.").style(Style::default().fg(Color::DarkGray)),
        Line::from(""),
    ];

    if let Some(list) = summary {
        if list.is_empty() {
            lines.push(Line::from("No recorded subjects yet.").style(Style::default().fg(Color::Yellow)));
            lines.push(Line::from(""));
            lines.push(Line::from("Add subjects in subjects.yaml and run the recording daemon:"));
            lines.push(Line::from("  python -m holespawn.record"));
        } else {
            lines.push(Line::from(format!("{} subject(s)", list.len())).style(Style::default().fg(Color::Cyan)));
            lines.push(Line::from(""));
            for r in list.iter() {
                let ts = r.last_timestamp.as_deref().unwrap_or("—");
                lines.push(Line::from(format!(
                    "  {}   last: {}   snapshots: {}   records: {}",
                    r.subject_id, ts, r.snapshot_count, r.record_count
                )));
            }
        }
    } else {
        lines.push(Line::from("(No data — open tab again to run: python -m holespawn.temporal --list-subjects)"));
    }

    lines.push(Line::from(""));
    lines.push(Line::from("[Esc] Back  [5] This tab"));

    let paragraph = Paragraph::new(lines).wrap(Wrap { trim: true });
    frame.render_widget(paragraph, inner);
}
