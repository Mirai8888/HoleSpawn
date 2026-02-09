//! App state machine and navigation.

use crate::data::{load_network, load_network_report};
use crate::event::{handle_key, next_tab_view, prev_tab_view, Action, View};
use crate::types::{NetworkAnalysis, ProfileEntry};
use std::path::PathBuf;

/// State for "Run pipeline" flow: target input -> network y/n -> spawn.
#[derive(Debug, Clone)]
pub enum RunPipelineStep {
    /// User is typing target (Twitter @username).
    TargetInput,
    /// Ask: Network? (y/n).
    NetworkConfirm,
    /// Pipeline started; message to show; Esc to close.
    Started(String),
}

#[derive(Debug, Clone)]
pub struct RunPipelineState {
    pub step: RunPipelineStep,
    pub target: String,
    pub want_network: Option<bool>,
}

pub struct App {
    pub profiles: Vec<ProfileEntry>,
    pub selected_index: usize,
    pub view: View,
    pub scroll: u16,
    pub compare_left: Option<usize>,
    pub compare_right: Option<usize>,
    pub network: Option<NetworkAnalysis>,
    pub network_report: Option<String>,
    pub live_path: Option<PathBuf>,
    pub show_help: bool,
    /// For NetworkGraph: selected node index in network.nodes
    pub selected_node_index: Option<usize>,
    pub search_mode: bool,
    pub search_query: String,
    /// When Some, we're in the "Run pipeline" prompt flow (modal).
    pub run_pipeline: Option<RunPipelineState>,
}

impl App {
    pub fn new(profiles: Vec<ProfileEntry>) -> Self {
        let selected_index = profiles.len().saturating_sub(1).min(profiles.len());
        Self {
            selected_index: if profiles.is_empty() { 0 } else { selected_index },
            profiles,
            view: View::Browser,
            scroll: 0,
            compare_left: None,
            compare_right: None,
            network: None,
            network_report: None,
            live_path: None,
            show_help: false,
            selected_node_index: None,
            search_mode: false,
            search_query: String::new(),
            run_pipeline: None,
        }
    }

    pub fn selected_profile(&self) -> Option<&ProfileEntry> {
        self.profiles.get(self.selected_index)
    }

    pub fn selected_profile_mut(&mut self) -> Option<&mut ProfileEntry> {
        self.profiles.get_mut(self.selected_index)
    }

    /// Indices into profiles that match current search (empty query = all).
    pub fn filtered_indices(&self) -> Vec<usize> {
        let q = self.search_query.to_lowercase();
        if q.is_empty() {
            return (0..self.profiles.len()).collect();
        }
        self.profiles
            .iter()
            .enumerate()
            .filter(|(_, p)| p.dir_name.to_lowercase().contains(&q))
            .map(|(i, _)| i)
            .collect()
    }

    pub fn load_network_for_selected(&mut self) {
        let path = self.selected_profile().map(|p| p.path.clone());
        if let Some(path) = path {
            self.network = load_network(&path);
            self.network_report = load_network_report(&path);
        }
    }

    pub fn dispatch(&mut self, action: Action) -> bool {
        let mut quit = false;
        match action {
            Action::Quit => quit = true,
            Action::NextItem => {
                let filtered = self.filtered_indices();
                if filtered.is_empty() {
                    return quit;
                }
                let pos = filtered.iter().position(|&i| i == self.selected_index);
                let pos = pos.unwrap_or(0);
                let next_pos = (pos + 1) % filtered.len();
                self.selected_index = filtered[next_pos];
                self.scroll = 0;
            }
            Action::PrevItem => {
                let filtered = self.filtered_indices();
                if filtered.is_empty() {
                    return quit;
                }
                let pos = filtered.iter().position(|&i| i == self.selected_index);
                let pos = pos.unwrap_or(0);
                let next_pos = (filtered.len() + pos - 1) % filtered.len();
                self.selected_index = filtered[next_pos];
                self.scroll = 0;
            }
            Action::SelectItem => {
                if self.selected_profile().is_some() {
                    self.view = View::Profile;
                    self.scroll = 0;
                }
            }
            Action::Protocol => {
                if self.selected_profile().is_some() {
                    self.view = View::Protocol;
                    self.scroll = 0;
                }
            }
            Action::Network => {
                if self.selected_profile().is_some() {
                    self.load_network_for_selected();
                    self.view = View::Network;
                    self.scroll = 0;
                }
            }
            Action::Compare => {
                self.view = View::Compare;
                self.compare_left = Some(self.selected_index);
                self.compare_right = if self.profiles.len() > 1 {
                    Some((self.selected_index + 1) % self.profiles.len())
                } else {
                    None
                };
                self.scroll = 0;
            }
            Action::Live => self.view = View::Live,
            Action::NextTab => {
                self.view = next_tab_view(self.view);
                if self.view == View::Network {
                    self.load_network_for_selected();
                }
                if self.view == View::Compare && self.compare_left.is_none() {
                    self.compare_left = Some(self.selected_index);
                    self.compare_right = if self.profiles.len() > 1 {
                        Some((self.selected_index + 1) % self.profiles.len())
                    } else {
                        None
                    };
                }
                self.scroll = 0;
            }
            Action::PrevTab => {
                self.view = prev_tab_view(self.view);
                if self.view == View::Network {
                    self.load_network_for_selected();
                }
                if self.view == View::Compare && self.compare_left.is_none() {
                    self.compare_left = Some(self.selected_index);
                    self.compare_right = if self.profiles.len() > 1 {
                        Some((self.selected_index + 1) % self.profiles.len())
                    } else {
                        None
                    };
                }
                self.scroll = 0;
            }
            Action::GotoTab(i) => {
                self.view = match i {
                    0 => View::Browser,
                    1 => {
                        self.load_network_for_selected();
                        View::Network
                    }
                    2 => {
                        if self.compare_left.is_none() {
                            self.compare_left = Some(self.selected_index);
                            self.compare_right = if self.profiles.len() > 1 {
                                Some((self.selected_index + 1) % self.profiles.len())
                            } else {
                                None
                            };
                        }
                        View::Compare
                    }
                    3 => View::Live,
                    _ => self.view,
                };
                self.scroll = 0;
            }
            Action::Search => self.search_mode = true,
            Action::Help => self.show_help = !self.show_help,
            Action::Back => {
                if self.show_help {
                    self.show_help = false;
                } else if self.search_mode {
                    self.search_mode = false;
                    self.search_query.clear();
                } else {
                    self.view = View::Browser;
                    self.scroll = 0;
                    self.network = None;
                    self.network_report = None;
                    self.selected_node_index = None;
                }
            }
            Action::ScrollUp => self.scroll = self.scroll.saturating_sub(1),
            Action::ScrollDown => self.scroll += 1,
            Action::PageUp => self.scroll = self.scroll.saturating_sub(20),
            Action::PageDown => self.scroll += 20,
            Action::Graph => {
                self.view = View::NetworkGraph;
                self.selected_node_index = Some(0);
                self.scroll = 0;
            }
            Action::NetworkReport => {
                self.view = View::NetworkReport;
                self.scroll = 0;
            }
            Action::NodeDetail => {
                if self.selected_node_index.is_some() {
                    self.view = View::NodeDetail;
                    self.scroll = 0;
                }
            }
            Action::NextNode => {
                if let Some(net) = &self.network {
                    let n = net.nodes.len();
                    if n > 0 {
                        let i = self.selected_node_index.unwrap_or(0);
                        self.selected_node_index = Some((i + 1) % n);
                    }
                }
            }
            Action::PrevNode => {
                if let Some(net) = &self.network {
                    let n = net.nodes.len();
                    if n > 0 {
                        let i = self.selected_node_index.unwrap_or(0);
                        self.selected_node_index = Some((n + i - 1) % n);
                    }
                }
            }
            Action::SelectLeft => {
                if self.view == View::Compare && self.profiles.len() > 0 {
                    let idx = self.compare_left.unwrap_or(0);
                    self.compare_left = Some((idx + self.profiles.len() - 1) % self.profiles.len());
                }
            }
            Action::SelectRight => {
                if self.view == View::Compare && self.profiles.len() > 0 {
                    let idx = self.compare_right.unwrap_or(0);
                    self.compare_right = Some((idx + 1) % self.profiles.len());
                }
            }
            Action::RunPipeline => {
                self.run_pipeline = Some(RunPipelineState {
                    step: RunPipelineStep::TargetInput,
                    target: String::new(),
                    want_network: None,
                });
            }
            Action::CycleCommunity => {}
            Action::None => {}
        }
        quit
    }

    /// Spawn the HoleSpawn Python pipeline. Returns a message for the user.
    pub fn spawn_pipeline(&self, target: &str, want_network: bool) -> String {
        let target = target.trim().trim_start_matches('@');
        if target.is_empty() {
            return "Target is empty. Enter a Twitter username (e.g. user or @user).".to_string();
        }
        let username = format!("@{}", target);
        let repo_root = self.repo_root();
        let mut cmd = std::process::Command::new("python");
        cmd.arg("-m")
            .arg("holespawn.build_site")
            .arg("--twitter-username")
            .arg(&username)
            .arg("--consent-acknowledged");
        if want_network {
            cmd.arg("--network");
        }
        cmd.current_dir(&repo_root);
        cmd.env_remove("PYTHONPATH"); // avoid conflicts; Python finds holespawn from repo root
        match cmd.spawn() {
            Ok(_) => {
                let out_base = self
                    .live_path
                    .as_deref()
                    .map(|p| p.display().to_string())
                    .unwrap_or_else(|| "outputs".to_string());
                format!(
                    "Pipeline started for {} (network: {}).\nOutput: {} — check Live tab.",
                    username,
                    if want_network { "yes" } else { "no" },
                    out_base
                )
            }
            Err(e) => format!("Failed to start pipeline: {}. Is Python in PATH?", e),
        }
    }

    /// Project root (parent of holespawn-tui if cwd is holespawn-tui).
    fn repo_root(&self) -> PathBuf {
        match std::env::current_dir() {
            Ok(cwd) => {
                if cwd.file_name().and_then(|n| n.to_str()) == Some("holespawn-tui") {
                    cwd.parent().unwrap_or(&cwd).to_path_buf()
                } else {
                    cwd
                }
            }
            _ => PathBuf::from("."),
        }
    }

    pub fn on_key(&mut self, key: crossterm::event::KeyEvent) -> bool {
        if let Some(mut rp) = self.run_pipeline.take() {
            use crate::app::RunPipelineStep;
            use crossterm::event::KeyCode;
            let mut put_back = true;
            match &rp.step {
                RunPipelineStep::TargetInput => match key.code {
                    KeyCode::Char(c) => rp.target.push(c),
                    KeyCode::Backspace => {
                        rp.target.pop();
                    }
                    KeyCode::Enter => {
                        rp.step = RunPipelineStep::NetworkConfirm;
                    }
                    KeyCode::Esc => put_back = false,
                    _ => {}
                },
                RunPipelineStep::NetworkConfirm => match key.code {
                    KeyCode::Char('y') | KeyCode::Char('Y') => {
                        let target = rp.target.clone();
                        let msg = self.spawn_pipeline(&target, true);
                        rp.step = RunPipelineStep::Started(msg);
                    }
                    KeyCode::Char('n') | KeyCode::Char('N') => {
                        let target = rp.target.clone();
                        let msg = self.spawn_pipeline(&target, false);
                        rp.step = RunPipelineStep::Started(msg);
                    }
                    KeyCode::Esc => put_back = false,
                    _ => {}
                },
                RunPipelineStep::Started(_) => {
                    if key.code == KeyCode::Esc {
                        put_back = false;
                    }
                }
            }
            if put_back {
                self.run_pipeline = Some(rp);
            }
            return false;
        }
        if self.search_mode && self.view == View::Browser {
            match key.code {
                crossterm::event::KeyCode::Char(c) => {
                    self.search_query.push(c);
                }
                crossterm::event::KeyCode::Backspace => {
                    self.search_query.pop();
                }
                crossterm::event::KeyCode::Enter => {
                    self.search_mode = false;
                }
                crossterm::event::KeyCode::Esc => {
                    self.search_mode = false;
                    self.search_query.clear();
                }
                _ => {}
            }
            return false;
        }
        let view = if self.show_help {
            View::Help
        } else {
            self.view
        };
        let action = handle_key(key, view);
        self.dispatch(action)
    }
}
