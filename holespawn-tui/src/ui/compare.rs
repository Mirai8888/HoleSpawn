//! Compare view: side-by-side two profiles (sentiment, themes, interests).

use crate::app::App;
use ratatui::prelude::*;
use ratatui::widgets::*;

fn bar(v: f64) -> String {
    let n = (v * 10.0).round() as usize;
    let n = n.min(10);
    format!("{}{}", "█".repeat(n), "░".repeat(10 - n))
}

pub fn draw(frame: &mut Frame, app: &App, area: Rect) {
    let margin = Margin::new(1, 1);
    let block = Block::default()
        .title(" Compare Profiles ")
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded);
    frame.render_widget(&block, area);
    let inner = block.inner(area).inner(&margin);

    let chunks = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(50), Constraint::Percentage(50)])
        .split(inner);

    let left_idx = app.compare_left.unwrap_or(0);
    let right_idx = app.compare_right.unwrap_or_else(|| if app.profiles.len() > 1 { 1 } else { 0 });
    let left = app.profiles.get(left_idx);
    let right = app.profiles.get(right_idx);

    let mut left_lines: Vec<Line> = vec![
        Line::from("← Left  [←] [→] change").style(Style::default().fg(Color::Cyan)),
        Line::from(""),
    ];
    if let Some(p) = left {
        left_lines.push(Line::from(p.dir_name.as_str()));
        left_lines.push(Line::from(""));
        if let Some(m) = &p.matrix {
            left_lines.push(Line::from("Sentiment:"));
            left_lines.push(Line::from(format!("  Pos {} {:.2}", bar(m.sentiment_positive), m.sentiment_positive)));
            left_lines.push(Line::from(format!("  Neg {} {:.2}", bar(m.sentiment_negative), m.sentiment_negative)));
            left_lines.push(Line::from(format!("  Neu {} {:.2}", bar(m.sentiment_neutral), m.sentiment_neutral)));
            left_lines.push(Line::from(""));
            if !m.themes.is_empty() {
                let theme_str: String = m.themes.iter().take(5).filter_map(|t| t.get(0).and_then(|v| v.as_str())).collect::<Vec<_>>().join(", ");
                left_lines.push(Line::from("Themes:"));
                left_lines.push(Line::from(format!("  {}", theme_str)));
                left_lines.push(Line::from(""));
            }
            if !m.specific_interests.is_empty() {
                left_lines.push(Line::from("Interests:"));
                left_lines.push(Line::from(format!("  {}", m.specific_interests[..m.specific_interests.len().min(6)].join(", "))));
            }
        } else {
            left_lines.push(Line::from("(No matrix)"));
        }
    } else {
        left_lines.push(Line::from("(No profile)"));
    }

    let mut right_lines: Vec<Line> = vec![
        Line::from("Right →  [←] [→] change").style(Style::default().fg(Color::Cyan)),
        Line::from(""),
    ];
    if let Some(p) = right {
        right_lines.push(Line::from(p.dir_name.as_str()));
        right_lines.push(Line::from(""));
        if let Some(m) = &p.matrix {
            right_lines.push(Line::from("Sentiment:"));
            right_lines.push(Line::from(format!("  Pos {} {:.2}", bar(m.sentiment_positive), m.sentiment_positive)));
            right_lines.push(Line::from(format!("  Neg {} {:.2}", bar(m.sentiment_negative), m.sentiment_negative)));
            right_lines.push(Line::from(format!("  Neu {} {:.2}", bar(m.sentiment_neutral), m.sentiment_neutral)));
            right_lines.push(Line::from(""));
            if !m.themes.is_empty() {
                let theme_str: String = m.themes.iter().take(5).filter_map(|t| t.get(0).and_then(|v| v.as_str())).collect::<Vec<_>>().join(", ");
                right_lines.push(Line::from("Themes:"));
                right_lines.push(Line::from(format!("  {}", theme_str)));
                right_lines.push(Line::from(""));
            }
            if !m.specific_interests.is_empty() {
                right_lines.push(Line::from("Interests:"));
                right_lines.push(Line::from(format!("  {}", m.specific_interests[..m.specific_interests.len().min(6)].join(", "))));
            }
        } else {
            right_lines.push(Line::from("(No matrix)"));
        }
    } else {
        right_lines.push(Line::from("(No profile)"));
    }

    let left_p = Paragraph::new(left_lines).scroll((app.scroll, 0)).wrap(Wrap { trim: true });
    let right_p = Paragraph::new(right_lines).scroll((app.scroll, 0)).wrap(Wrap { trim: true });
    frame.render_widget(left_p, chunks[0]);
    frame.render_widget(right_p, chunks[1]);
}
