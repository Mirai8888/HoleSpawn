//! Shared types for HoleSpawn TUI. Deserialize from HoleSpawn JSON output; use #[serde(default)] for compatibility.

use serde::Deserialize;
use std::collections::HashMap;
use std::path::PathBuf;

/// behavioral_matrix.json — psychological profile from HoleSpawn.
#[derive(Debug, Clone, Deserialize)]
pub struct BehavioralMatrix {
    /// Themes: list of [word, frequency] from HoleSpawn
    #[serde(default)]
    pub themes: Vec<Vec<serde_json::Value>>,
    #[serde(default)]
    pub sentiment_compound: f64,
    #[serde(default)]
    pub sentiment_positive: f64,
    #[serde(default)]
    pub sentiment_negative: f64,
    #[serde(default)]
    pub sentiment_neutral: f64,
    #[serde(default)]
    pub avg_sentence_length: f64,
    #[serde(default)]
    pub avg_word_length: f64,
    #[serde(default)]
    pub question_ratio: f64,
    #[serde(default)]
    pub sample_phrases: Vec<String>,
    #[serde(default)]
    pub communication_style: String,
    #[serde(default)]
    pub specific_interests: Vec<String>,
    #[serde(default)]
    pub obsessions: Vec<String>,
    #[serde(default)]
    pub vocabulary_sample: Vec<String>,
    #[serde(flatten)]
    pub extra: HashMap<String, serde_json::Value>,
}

/// Recording summary for one subject (from `python -m holespawn.temporal --list-subjects`).
#[derive(Debug, Clone, serde::Deserialize)]
pub struct RecordingSummary {
    #[serde(default)]
    pub subject_id: String,
    pub last_timestamp: Option<String>,
    #[serde(default)]
    pub snapshot_count: u64,
    #[serde(default)]
    pub record_count: u64,
}

/// One profile entry (one output directory).
#[derive(Debug, Clone)]
pub struct ProfileEntry {
    pub dir_name: String,
    pub path: PathBuf,
    pub username: String,
    pub timestamp: String,
    pub matrix: Option<BehavioralMatrix>,
    pub protocol: Option<String>,
    pub has_network: bool,
}

/// network_analysis.json — graph and community data.
#[derive(Debug, Clone, Deserialize)]
pub struct NetworkAnalysis {
    #[serde(default)]
    pub nodes: Vec<String>,
    #[serde(default)]
    pub edges: Vec<NetworkEdge>,
    /// community_id (as string) -> list of usernames
    #[serde(default)]
    pub communities: HashMap<String, Vec<String>>,
    #[serde(default)]
    pub community_metrics: HashMap<String, CommunityMetrics>,
    #[serde(default)]
    pub node_metrics: HashMap<String, NodeMetrics>,
    #[serde(default)]
    pub bridge_nodes: Vec<BridgeNode>,
    #[serde(default)]
    pub amplifiers: Vec<BridgeNode>,
    #[serde(default)]
    pub gatekeepers: Vec<GatekeeperNode>,
    #[serde(default)]
    pub vulnerable_entry_points: Vec<VulnerableNode>,
    #[serde(default)]
    pub sanity_check: SanityCheck,
    #[serde(default)]
    pub betweenness: HashMap<String, f64>,
    #[serde(default)]
    pub in_degree: HashMap<String, u32>,
    #[serde(default)]
    pub out_degree: HashMap<String, u32>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct NetworkEdge {
    pub source: String,
    pub target: String,
    #[serde(default = "one_f64")]
    pub weight: f64,
}

fn one_f64() -> f64 {
    1.0
}

#[derive(Debug, Clone, Deserialize)]
pub struct CommunityMetrics {
    #[serde(default)]
    pub size: usize,
    #[serde(default)]
    pub density: f64,
    pub hub_node: Option<String>,
    #[serde(default)]
    pub bridge_count: usize,
    #[serde(default)]
    pub themes: Option<Vec<String>>,
    pub description: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct NodeMetrics {
    #[serde(default)]
    pub degree: usize,
    #[serde(default)]
    pub in_degree: usize,
    #[serde(default)]
    pub out_degree: usize,
    #[serde(default)]
    pub betweenness: f64,
    pub eigenvector: Option<f64>,
    #[serde(default)]
    pub community: i64,
    #[serde(default)]
    pub role: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct BridgeNode {
    pub username: String,
    #[serde(default)]
    pub betweenness: f64,
    #[serde(default)]
    pub communities_connected: Vec<u32>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct GatekeeperNode {
    pub username: String,
    #[serde(default)]
    pub community_id: u32,
    #[serde(default)]
    pub internal_degree: usize,
    #[serde(default)]
    pub external_degree: usize,
}

#[derive(Debug, Clone, Deserialize)]
pub struct VulnerableNode {
    pub username: String,
    #[serde(default)]
    pub reason: String,
    #[serde(default)]
    pub connected_to: Vec<String>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct SanityCheck {
    #[serde(default)]
    pub n_nodes: usize,
    #[serde(default)]
    pub n_edges: usize,
    #[serde(default)]
    pub n_communities: usize,
    #[serde(default)]
    pub density: f64,
    #[serde(default)]
    pub is_valid: bool,
}

/// Node profile from network (if we had node_profiles in JSON; otherwise derived from node_metrics + report).
#[derive(Debug, Clone, Deserialize)]
pub struct NodeProfileData {
    pub username: String,
    #[serde(default)]
    pub community_id: String,
    #[serde(default)]
    pub role: String,
    pub strategic_value_score: Option<u32>,
    pub information_role: Option<String>,
    pub approach_vectors: Option<Vec<String>>,
    pub cascade_potential: Option<CascadePotential>,
    pub resistance_factors: Option<Vec<String>>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct CascadePotential {
    pub estimated_reach: Option<usize>,
    pub hops: Option<usize>,
    pub communities_affected: Option<Vec<u32>>,
}
