use crate::app::App;
use ratatui::prelude::*;
use ratatui::widgets::*;

pub fn draw(frame: &mut Frame, _app: &App, area: Rect) {
    let block = Block::default()
        .title(" Help ")
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded);
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let text = r#"
Tabs:  [1] Profiles  [2] Network  [3] Compare  [4] Live   Tab / Shift+Tab  cycle

Browser:
  j / Down    Next profile
  k / Up      Previous profile
  Enter       Full profile view
  b           Binding protocol
  n           Network view
  c           Compare two profiles
  /           Search (filter list), Enter/Esc to confirm
  R           Run pipeline (target + network y/n)
  ?           This help
  q           Quit

Profile / Protocol / Network / Report:
  Esc         Back
  j / Down    Scroll down
  k / Up      Scroll up
  d / PgDn    Page down
  u / PgUp    Page up

Network:  [g] Graph  [r] Report
Graph:    j/k node, Enter detail, [r] report
Compare:  ← → change left/right profile
"#;
    let paragraph = Paragraph::new(text).wrap(Wrap { trim: true });
    frame.render_widget(paragraph, inner);
}
