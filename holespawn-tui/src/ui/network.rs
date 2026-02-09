use crate::app::App;
use ratatui::prelude::*;
use ratatui::widgets::*;

pub fn draw(frame: &mut Frame, app: &App, area: Rect) {
    let margin = Margin::new(1, 1);
    let margin_bottom = Margin::new(1, 0);
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Min(3), Constraint::Length(3)])
        .split(area);
    let block = Block::default()
        .title(" Network ")
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded);
    frame.render_widget(block, area);
    if let Some(net) = &app.network {
        let text = format!(
            "Nodes: {}  Edges: {}  Communities: {}  Density: {:.4}",
            net.nodes.len(),
            net.edges.len(),
            net.communities.len(),
            net.sanity_check.density
        );
        let p = Paragraph::new(text).wrap(Wrap { trim: true });
        frame.render_widget(p, chunks[0].inner(&margin));
    } else {
        let p = Paragraph::new("No network data. Run HoleSpawn with --network for this profile.")
            .wrap(Wrap { trim: true });
        frame.render_widget(p, chunks[0].inner(&margin));
    }
    let hint = Paragraph::new("[Esc] Back  [g] Graph  [r] Report");
    frame.render_widget(hint, chunks[1].inner(&margin_bottom));
}
