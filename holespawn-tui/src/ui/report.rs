//! Network report view: network_report.md with scroll.

use crate::app::App;
use ratatui::prelude::*;
use ratatui::widgets::*;

pub fn draw(frame: &mut Frame, app: &App, area: Rect) {
    let block = Block::default()
        .title(" Network Report ")
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded);
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let text = app
        .network_report
        .as_deref()
        .unwrap_or("(No network_report.md)");
    let paragraph = Paragraph::new(text)
        .scroll((app.scroll, 0))
        .wrap(Wrap { trim: true });
    frame.render_widget(paragraph, inner);
}
