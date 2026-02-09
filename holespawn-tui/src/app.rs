//! App state machine and navigation.

use crate::data::{load_network, load_network_report};
use crate::event::{handle_key, next_tab_view, prev_tab_view, Action, View};
use crate::types::{NetworkAnalysis, ProfileEntry};
use std::path::PathBuf;

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
            Action::CycleCommunity => {}
            Action::None => {}
        }
        quit
    }

    pub fn on_key(&mut self, key: crossterm::event::KeyEvent) -> bool {
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
