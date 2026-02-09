//! Scan output directories for HoleSpawn profiles (YYYYMMDD_HHMMSS_username).

use crate::data::load_matrix;
use crate::types::ProfileEntry;
use std::path::Path;

/// Pattern: YYYYMMDD_HHMMSS_username (e.g. 20260208_143022_target1)
fn parse_dir_name(name: &str) -> Option<(String, String)> {
    let parts: Vec<&str> = name.splitn(3, '_').collect();
    if parts.len() >= 3 {
        let timestamp = format!("{}_{}", parts[0], parts[1]);
        let username = parts[2].to_string();
        return Some((timestamp, username));
    }
    if parts.len() == 2 {
        let timestamp = parts[0].to_string();
        let username = parts[1].to_string();
        return Some((timestamp, username));
    }
    None
}

/// If base_path itself contains behavioral_matrix.json, treat it as a single profile.
fn try_single_dir(base: &Path) -> Option<ProfileEntry> {
    if !base.join("behavioral_matrix.json").exists() {
        return None;
    }
    let name = base
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("run")
        .to_string();
    let (timestamp, username) = parse_dir_name(&name).unwrap_or_else(|| (name.clone(), name.clone()));
    let matrix = load_matrix(base);
    let protocol = std::fs::read_to_string(base.join("binding_protocol.md")).ok();
    let has_network = base.join("network_analysis.json").exists();
    Some(ProfileEntry {
        dir_name: name.clone(),
        path: base.to_path_buf(),
        username,
        timestamp,
        matrix,
        protocol,
        has_network,
    })
}

/// Walk base_path for subdirs matching profile pattern; load matrix, protocol, and set has_network.
pub fn scan_output_dirs(base_path: &Path) -> Vec<ProfileEntry> {
    let mut entries = Vec::new();
    let base = match base_path.canonicalize() {
        Ok(p) => p,
        Err(_) => return entries,
    };
    if let Some(one) = try_single_dir(&base) {
        return vec![one];
    }
    let read_dir = match std::fs::read_dir(&base) {
        Ok(d) => d,
        Err(_) => return entries,
    };
    for item in read_dir.flatten() {
        let path = item.path();
        if !path.is_dir() {
            continue;
        }
        let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("");
        let (timestamp, username) = match parse_dir_name(name) {
            Some(p) => p,
            None => continue,
        };
        let matrix = load_matrix(&path);
        let protocol = std::fs::read_to_string(path.join("binding_protocol.md")).ok();
        let has_network = path.join("network_analysis.json").exists();
        entries.push(ProfileEntry {
            dir_name: name.to_string(),
            path,
            username,
            timestamp,
            matrix,
            protocol,
            has_network,
        });
    }
    entries.sort_by(|a, b| b.timestamp.cmp(&a.timestamp));
    entries
}
