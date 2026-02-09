mod browser;
mod compare;
mod graph;
mod help;
mod live;
mod network;
mod node_detail;
mod profile;
mod protocol;
mod report;

use crate::app::App;
use crate::event::{active_tab_index, View};
use ratatui::layout::{Constraint, Direction, Layout};
use ratatui::style::{Color, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::Paragraph;

pub fn draw(frame: &mut ratatui::Frame, app: &App) {
    let area = frame.size();
    if app.show_help {
        help::draw(frame, app, area);
        return;
    }
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Length(1), Constraint::Min(1)])
        .split(area);
    let tab_names = ["[1] Profiles", "[2] Network", "[3] Compare", "[4] Live"];
    let active = active_tab_index(app.view);
    let tab_style = |i: usize| {
        if i == active {
            Style::default().fg(Color::Black).bg(Color::Cyan)
        } else {
            Style::default()
        }
    };
    let spans: Vec<Span> = tab_names
        .iter()
        .enumerate()
        .flat_map(|(i, n)| {
            [
                Span::styled(format!(" {} ", n), tab_style(i)),
                Span::raw(if i < tab_names.len() - 1 { " " } else { "" }),
            ]
        })
        .collect();
    let tab_paragraph = Paragraph::new(Line::from(spans));
    frame.render_widget(tab_paragraph, chunks[0]);
    let content = chunks[1];
    match app.view {
        View::Browser => browser::draw(frame, app, content),
        View::Profile => profile::draw(frame, app, content),
        View::Protocol => protocol::draw(frame, app, content),
        View::Network => network::draw(frame, app, content),
        View::NetworkGraph => graph::draw(frame, app, content),
        View::NetworkReport => report::draw(frame, app, content),
        View::NodeDetail => node_detail::draw(frame, app, content),
        View::Compare => compare::draw(frame, app, content),
        View::Live => live::draw(frame, app, content),
        View::Help => browser::draw(frame, app, content),
    }
}
