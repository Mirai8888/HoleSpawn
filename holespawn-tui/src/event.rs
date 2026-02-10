//! Input handling and actions.

use crossterm::event::{KeyCode, KeyEvent, KeyModifiers};
use std::io;

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum View {
    Browser,
    Profile,
    Protocol,
    Network,
    NetworkGraph,
    NetworkReport,
    NodeDetail,
    Compare,
    Live,
    Recording,
    Help,
}

#[derive(Debug, Clone)]
pub enum Action {
    Quit,
    None,
    NextItem,
    PrevItem,
    SelectItem,
    Protocol,
    Network,
    Compare,
    Live,
    NextTab,
    PrevTab,
    GotoTab(usize),
    Search,
    Help,
    Back,
    ScrollUp,
    ScrollDown,
    PageUp,
    PageDown,
    CycleCommunity,
    Graph,
    NodeDetail,
    NetworkReport,
    NextNode,
    PrevNode,
    SelectLeft,
    SelectRight,
    /// Delete the currently selected profile/run directory.
    DeleteProfile,
    /// Open "Run pipeline" prompt (target + network y/n).
    RunPipeline,
}

pub fn next_tab_view(v: View) -> View {
    match v {
        View::Browser | View::Profile | View::Protocol | View::NodeDetail => View::Network,
        View::Network | View::NetworkGraph | View::NetworkReport => View::Compare,
        View::Compare => View::Live,
        View::Live => View::Recording,
        View::Recording => View::Browser,
        View::Help => View::Browser,
    }
}

pub fn prev_tab_view(v: View) -> View {
    match v {
        View::Browser => View::Recording,
        View::Profile | View::Protocol | View::NodeDetail => View::Browser,
        View::Network | View::NetworkGraph | View::NetworkReport => View::Browser,
        View::Compare => View::Network,
        View::Live => View::Compare,
        View::Recording => View::Live,
        View::Help => View::Browser,
    }
}

pub fn active_tab_index(view: View) -> usize {
    match view {
        View::Browser | View::Profile | View::Protocol | View::NodeDetail => 0,
        View::Network | View::NetworkGraph | View::NetworkReport => 1,
        View::Compare => 2,
        View::Live => 3,
        View::Recording => 4,
        View::Help => 0,
    }
}

pub fn handle_key(key: KeyEvent, view: View) -> Action {
    let code = key.code;
    let _shift = key.modifiers.contains(KeyModifiers::SHIFT);
    match view {
        View::Browser => match code {
            KeyCode::Char('q') => Action::Quit,
            KeyCode::Char('j') | KeyCode::Down => Action::NextItem,
            KeyCode::Char('k') | KeyCode::Up => Action::PrevItem,
            KeyCode::Enter => Action::SelectItem,
            KeyCode::Char('b') => Action::Protocol,
            KeyCode::Char('n') => Action::Network,
            KeyCode::Char('c') => Action::Compare,
            KeyCode::Char('l') => Action::Live,
            KeyCode::Char('1') => Action::GotoTab(0),
            KeyCode::Char('2') => Action::GotoTab(1),
            KeyCode::Char('3') => Action::GotoTab(2),
            KeyCode::Char('4') => Action::GotoTab(3),
            KeyCode::Char('5') => Action::GotoTab(4),
            KeyCode::Tab => Action::NextTab,
            KeyCode::BackTab => Action::PrevTab,
            KeyCode::Char('/') => Action::Search,
            KeyCode::Char('?') => Action::Help,
            // Use lowercase keys for ergonomics; avoid accidental repeats.
            KeyCode::Char('r') => Action::RunPipeline,
            KeyCode::Char('x') => Action::DeleteProfile,
            _ => Action::None,
        },
        View::Profile | View::Protocol => match code {
            KeyCode::Esc => Action::Back,
            KeyCode::Char('1') => Action::GotoTab(0),
            KeyCode::Char('2') => Action::GotoTab(1),
            KeyCode::Char('3') => Action::GotoTab(2),
            KeyCode::Char('4') => Action::GotoTab(3),
            KeyCode::Char('5') => Action::GotoTab(4),
            KeyCode::Char('j') | KeyCode::Down => Action::ScrollDown,
            KeyCode::Char('k') | KeyCode::Up => Action::ScrollUp,
            KeyCode::PageDown | KeyCode::Char('d') => Action::PageDown,
            KeyCode::PageUp | KeyCode::Char('u') => Action::PageUp,
            KeyCode::Char('b') => Action::Protocol,
            KeyCode::Char('n') => Action::Network,
            _ => Action::None,
        },
        View::NetworkGraph => match code {
            KeyCode::Esc => Action::Back,
            KeyCode::Char('1') => Action::GotoTab(0),
            KeyCode::Char('2') => Action::GotoTab(1),
            KeyCode::Char('3') => Action::GotoTab(2),
            KeyCode::Char('4') => Action::GotoTab(3),
            KeyCode::Char('5') => Action::GotoTab(4),
            KeyCode::Tab => Action::CycleCommunity,
            KeyCode::Enter => Action::NodeDetail,
            KeyCode::Char('r') => Action::NetworkReport,
            KeyCode::Char('j') | KeyCode::Down => Action::NextNode,
            KeyCode::Char('k') | KeyCode::Up => Action::PrevNode,
            _ => Action::None,
        },
        View::NodeDetail => match code {
            KeyCode::Esc => Action::Back,
            KeyCode::Char('1') => Action::GotoTab(0),
            KeyCode::Char('2') => Action::GotoTab(1),
            KeyCode::Char('3') => Action::GotoTab(2),
            KeyCode::Char('4') => Action::GotoTab(3),
            KeyCode::Char('5') => Action::GotoTab(4),
            KeyCode::Char('j') | KeyCode::Down => Action::ScrollDown,
            KeyCode::Char('k') | KeyCode::Up => Action::ScrollUp,
            KeyCode::PageDown | KeyCode::Char('d') => Action::PageDown,
            KeyCode::PageUp | KeyCode::Char('u') => Action::PageUp,
            _ => Action::None,
        },
        View::Compare => match code {
            KeyCode::Esc => Action::Back,
            KeyCode::Char('1') => Action::GotoTab(0),
            KeyCode::Char('2') => Action::GotoTab(1),
            KeyCode::Char('3') => Action::GotoTab(2),
            KeyCode::Char('4') => Action::GotoTab(3),
            KeyCode::Char('5') => Action::GotoTab(4),
            KeyCode::Left => Action::SelectLeft,
            KeyCode::Right => Action::SelectRight,
            KeyCode::Char('j') | KeyCode::Down => Action::ScrollDown,
            KeyCode::Char('k') | KeyCode::Up => Action::ScrollUp,
            _ => Action::None,
        },
        View::Live => match code {
            KeyCode::Esc => Action::Back,
            KeyCode::Char('1') => Action::GotoTab(0),
            KeyCode::Char('2') => Action::GotoTab(1),
            KeyCode::Char('3') => Action::GotoTab(2),
            KeyCode::Char('4') => Action::GotoTab(3),
            KeyCode::Char('5') => Action::GotoTab(4),
            _ => Action::None,
        },
        View::Recording => match code {
            KeyCode::Esc => Action::Back,
            KeyCode::Char('1') => Action::GotoTab(0),
            KeyCode::Char('2') => Action::GotoTab(1),
            KeyCode::Char('3') => Action::GotoTab(2),
            KeyCode::Char('4') => Action::GotoTab(3),
            KeyCode::Char('5') => Action::GotoTab(4),
            _ => Action::None,
        },
        View::Help => match code {
            KeyCode::Esc | KeyCode::Char('q') => Action::Back,
            _ => Action::None,
        },
        View::Network => match code {
            KeyCode::Esc => Action::Back,
            KeyCode::Char('1') => Action::GotoTab(0),
            KeyCode::Char('2') => Action::GotoTab(1),
            KeyCode::Char('3') => Action::GotoTab(2),
            KeyCode::Char('4') => Action::GotoTab(3),
            KeyCode::Char('5') => Action::GotoTab(4),
            KeyCode::Char('j') | KeyCode::Down => Action::ScrollDown,
            KeyCode::Char('k') | KeyCode::Up => Action::ScrollUp,
            KeyCode::Char('g') => Action::Graph,
            KeyCode::Char('r') => Action::NetworkReport,
            _ => Action::None,
        },
        View::NetworkReport => match code {
            KeyCode::Esc => Action::Back,
            KeyCode::Char('1') => Action::GotoTab(0),
            KeyCode::Char('2') => Action::GotoTab(1),
            KeyCode::Char('3') => Action::GotoTab(2),
            KeyCode::Char('4') => Action::GotoTab(3),
            KeyCode::Char('5') => Action::GotoTab(4),
            KeyCode::Char('j') | KeyCode::Down => Action::ScrollDown,
            KeyCode::Char('k') | KeyCode::Up => Action::ScrollUp,
            KeyCode::PageDown | KeyCode::Char('d') => Action::PageDown,
            KeyCode::PageUp | KeyCode::Char('u') => Action::PageUp,
            _ => Action::None,
        },
    }
}

pub fn poll_event() -> io::Result<Option<KeyEvent>> {
    if crossterm::event::poll(std::time::Duration::from_millis(100))? {
        if let crossterm::event::Event::Key(e) = crossterm::event::read()? {
            return Ok(Some(e));
        }
    }
    Ok(None)
}
