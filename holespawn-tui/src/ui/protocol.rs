use crate::app::App;
use ratatui::prelude::*;
use ratatui::widgets::*;

pub fn draw(frame: &mut Frame, app: &App, area: Rect) {
    let block = Block::default()
        .title(format!(
            " Binding Protocol: @{} ",
            app.selected_profile().map(|p| p.username.as_str()).unwrap_or("")
        ))
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded);
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let text = app
        .selected_profile()
        .and_then(|p| p.protocol.as_ref())
        .map(|s| s.as_str())
        .unwrap_or("(No binding_protocol.md)");
    let paragraph = Paragraph::new(text)
        .scroll((app.scroll, 0))
        .wrap(Wrap { trim: true });
    frame.render_widget(paragraph, inner);
}
