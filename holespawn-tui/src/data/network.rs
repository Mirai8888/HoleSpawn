use crate::types::NetworkAnalysis;
use std::path::Path;

/// Load network_analysis.json from a profile directory.
pub fn load_network(path: &Path) -> Option<NetworkAnalysis> {
    let file = path.join("network_analysis.json");
    if !file.exists() {
        return None;
    }
    let s = std::fs::read_to_string(&file).ok()?;
    serde_json::from_str(&s).ok()
}

/// Load network_report.md as raw string.
pub fn load_network_report(path: &Path) -> Option<String> {
    let file = path.join("network_report.md");
    if !file.exists() {
        return None;
    }
    std::fs::read_to_string(&file).ok()
}
