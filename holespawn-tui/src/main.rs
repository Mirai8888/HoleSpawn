//! HoleSpawn TUI — Terminal UI for cognitive profiling and network analysis output.

mod app;
mod config;
mod data;
mod event;
mod types;
mod ui;

use app::App;
use config::Config;
use crossterm::{
    event::{DisableMouseCapture, EnableMouseCapture},
    execute,
    terminal::{EnterAlternateScreen, LeaveAlternateScreen},
};
use data::scan_output_dirs;
use std::io::{self, stdout};
use std::path::PathBuf;
use std::time::Duration;
use ratatui::prelude::*;

fn run_app<B: Backend>(terminal: &mut Terminal<B>, app: &mut App) -> io::Result<bool> {
    loop {
        terminal.draw(|f| ui::draw(f, app))?;
        if crossterm::event::poll(Duration::from_millis(100))? {
            if let crossterm::event::Event::Key(key) = crossterm::event::read()? {
                if app.on_key(key) {
                    return Ok(true);
                }
            }
        }
    }
}

fn main() -> io::Result<()> {
    let mut args = std::env::args().skip(1);
    let output_path: Option<PathBuf> = args.next().map(PathBuf::from);
    let config = Config::load();
    let base = config.output_dir(output_path.as_deref());

    let profiles = if base.exists() {
        scan_output_dirs(&base)
    } else {
        Vec::new()
    };

    let mut app = App::new(profiles);
    app.live_path = Some(base.canonicalize().unwrap_or(base));

    let mut stdout = stdout();
    execute!(stdout, EnterAlternateScreen, EnableMouseCapture)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    let _ = run_app(&mut terminal, &mut app)?;

    execute!(
        terminal.backend_mut(),
        LeaveAlternateScreen,
        DisableMouseCapture
    )?;
    terminal.show_cursor()?;

    Ok(())
}
