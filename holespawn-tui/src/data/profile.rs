use crate::types::BehavioralMatrix;
use std::path::Path;

/// Load behavioral_matrix.json from a profile directory.
pub fn load_matrix(path: &Path) -> Option<BehavioralMatrix> {
    let file = path.join("behavioral_matrix.json");
    if !file.exists() {
        return None;
    }
    let s = std::fs::read_to_string(&file).ok()?;
    serde_json::from_str(&s).ok()
}
