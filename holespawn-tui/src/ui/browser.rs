use crate::app::App;
use ratatui::prelude::*;
use ratatui::widgets::*;

pub fn draw(frame: &mut Frame, app: &App, area: Rect) {
    let chunks = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Length(35), Constraint::Min(20)])
        .split(area);

    let filtered = app.filtered_indices();
    let title = format!(
        " HoleSpawn (穴卵) — {} profiles {} ",
        filtered.len(),
        if app.search_query.is_empty() { "" } else { "(filtered)" }
    );
    let block = Block::default()
        .title(title)
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded);
    frame.render_widget(block, area);

    let list_items: Vec<ListItem> = filtered
        .iter()
        .map(|&i| {
            let p = &app.profiles[i];
            let prefix = if i == app.selected_index { "▶ " } else { "  " };
            let line = format!("{}{}  {}", prefix, p.dir_name, if p.has_network { " [n]" } else { "" });
            ListItem::new(line)
        })
        .collect();
    let list_block = Block::default()
        .borders(Borders::RIGHT)
        .border_type(BorderType::Plain);
    let margin = Margin::new(1, 1);
    let inner = list_block.inner(chunks[0].inner(&margin));
    frame.render_widget(list_block, chunks[0].inner(&margin));
    let mut state = ListState::default();
    let selected_list_pos = filtered.iter().position(|&i| i == app.selected_index);
    state.select(selected_list_pos);
    let list = List::new(list_items).highlight_style(Style::default().bg(Color::DarkGray));
    frame.render_stateful_widget(list, inner, &mut state);

    // Right pane: preview of selected profile, or onboarding if none.
    let preview = chunks[1].inner(&margin);
    if app.profiles.is_empty() {
        let mut lines = vec![
            Line::from("No runs found yet.").style(Style::default().fg(Color::Yellow)),
            Line::from(""),
            Line::from("This TUI scans generated runs under:"),
            Line::from("  - outputs/   (default)"),
            Line::from("  - out/       (if present)"),
            Line::from(""),
            Line::from("To start a new run from here:").style(Style::default().fg(Color::Cyan)),
            Line::from("  r / R   Run pipeline (enter X handle, then choose network y/n)"),
            Line::from(""),
            Line::from("Or run pipeline manually, then restart TUI:"),
            Line::from("  python -m holespawn.build_site --twitter-username @user --network"),
            Line::from(""),
            Line::from("[?] Help  [q] Quit"),
        ];
        let paragraph = Paragraph::new(lines).wrap(Wrap { trim: true });
        frame.render_widget(paragraph, preview);
    } else if let Some(p) = app.selected_profile() {
        let mut lines = vec![
            Line::from("Behavioral Matrix").style(Style::default().fg(Color::Cyan)),
            Line::from(""),
        ];
        if let Some(m) = &p.matrix {
            lines.push(Line::from("Sentiment:"));
            lines.push(Line::from(format!(
                "  Positive ██████░░░░ {:.2}",
                m.sentiment_positive
            )));
            lines.push(Line::from(format!(
                "  Negative ████████░░ {:.2}",
                m.sentiment_negative
            )));
            lines.push(Line::from(format!("  Neutral  ███░░░░░░░ {:.2}", m.sentiment_neutral)));
            lines.push(Line::from(""));
            if !m.themes.is_empty() {
                let theme_str: String = m
                    .themes
                    .iter()
                    .take(5)
                    .filter_map(|t| {
                        if let Some(s) = t.get(0).and_then(|v| v.as_str()) {
                            Some(s.to_string())
                        } else {
                            None
                        }
                    })
                    .collect::<Vec<_>>()
                    .join(", ");
                lines.push(Line::from("Themes:"));
                lines.push(Line::from(format!("  {}", theme_str)));
            }
            if !m.specific_interests.is_empty() {
                lines.push(Line::from(""));
                lines.push(Line::from("Interests: ".to_string() + &m.specific_interests[..m.specific_interests.len().min(8)].join(", ")));
            }
        } else {
            lines.push(Line::from("(No behavioral_matrix.json)"));
        }
        lines.push(Line::from(""));
        lines.push(Line::from(
            "[Enter] Profile   [b] Protocol   [n] Network   [c] Compare   [/ ] Search   [r] Run pipeline   [x] Delete run",
        ));
        let paragraph = Paragraph::new(lines);
        frame.render_widget(paragraph, preview);
    }
    if app.search_mode {
        let search_line = format!("/ {}", app.search_query);
        let p = Paragraph::new(search_line).style(Style::default().fg(Color::Yellow));
        let area = Rect { x: 2, y: area.height.saturating_sub(1), width: area.width.saturating_sub(4), height: 1 };
        frame.render_widget(p, area);
    }
}
