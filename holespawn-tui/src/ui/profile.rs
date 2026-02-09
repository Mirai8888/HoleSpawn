use crate::app::App;
use ratatui::prelude::*;
use ratatui::widgets::*;

pub fn draw(frame: &mut Frame, app: &App, area: Rect) {
    let block = Block::default()
        .title(format!(" Profile: @{} ", app.selected_profile().map(|p| p.username.as_str()).unwrap_or("")))
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded);
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Min(10), Constraint::Length(3)])
        .split(inner);

    let mut lines: Vec<Line> = vec![
        Line::from("── Behavioral Matrix ──").style(Style::default().fg(Color::Cyan)),
        Line::from(""),
    ];
    if let Some(p) = app.selected_profile() {
        if let Some(m) = &p.matrix {
            lines.push(Line::from("Sentiment"));
            lines.push(Line::from(format!(
                "  Compound: {:.2}  Positive: {:.2}  Negative: {:.2}  Neutral: {:.2}",
                m.sentiment_compound,
                m.sentiment_positive,
                m.sentiment_negative,
                m.sentiment_neutral
            )));
            lines.push(Line::from(""));
            lines.push(Line::from("Linguistic"));
            lines.push(Line::from(format!(
                "  Avg sentence length: {:.1}  Question ratio: {:.2}",
                m.avg_sentence_length, m.question_ratio
            )));
            lines.push(Line::from(""));
            if !m.obsessions.is_empty() {
                lines.push(Line::from("Obsessions: ".to_string() + &m.obsessions.join(", ")));
            }
            if !m.specific_interests.is_empty() {
                lines.push(Line::from("Interests: ".to_string() + &m.specific_interests.join(", ")));
            }
            if !m.communication_style.is_empty() {
                lines.push(Line::from("Style: ".to_string() + &m.communication_style));
            }
        } else {
            lines.push(Line::from("(No matrix data)"));
        }
    }
    lines.push(Line::from(""));
    lines.push(Line::from("[b] Binding protocol  [n] Network  [Esc] Back"));

    let paragraph = Paragraph::new(lines)
        .scroll((app.scroll, 0))
        .wrap(Wrap { trim: true });
    frame.render_widget(paragraph, chunks[0]);
}
