//! Configuration loading from file and env.

use serde::Deserialize;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Deserialize)]
pub struct Config {
    /// Base output directory to scan for profiles (outputs/)
    #[serde(default)]
    pub output_dir: Option<PathBuf>,
    #[serde(default)]
    pub db_path: Option<PathBuf>,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            output_dir: None,
            db_path: None,
        }
    }
}

impl Config {
    /// Load from ~/.config/holespawn/config.toml or current dir config.toml
    pub fn load() -> Self {
        let paths = [
            dirs::config_dir()
                .map(|d| d.join("holespawn").join("config.toml")),
            Some(PathBuf::from("config.toml")),
            Some(PathBuf::from("holespawn-tui").join("config.toml")),
        ];
        for path in paths.into_iter().flatten() {
            if path.exists() {
                if let Ok(s) = std::fs::read_to_string(&path) {
                    if let Ok(c) = toml::from_str(&s) {
                        return c;
                    }
                }
            }
        }
        Self::default()
    }

    /// Resolve output directory:
    /// 1) CLI override
    /// 2) config file
    /// 3) existing "outputs" or "out" directory
    /// 4) default "outputs"
    pub fn output_dir(&self, cli_path: Option<&Path>) -> PathBuf {
        if let Some(p) = cli_path {
            return p.to_path_buf();
        }
        if let Some(cfg) = &self.output_dir {
            return cfg.clone();
        }
        if Path::new("outputs").exists() {
            return PathBuf::from("outputs");
        }
        if Path::new("out").exists() {
            return PathBuf::from("out");
        }
        PathBuf::from("outputs")
    }
}
