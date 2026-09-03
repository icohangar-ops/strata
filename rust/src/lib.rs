use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AttributeInput {
    pub level: String,
    pub score: i32,
    pub anchor: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CharacteristicInput {
    pub id: String,
    pub name: String,
    pub weight: f64,
    pub attributes: Vec<AttributeInput>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GroupInput {
    pub id: String,
    pub name: String,
    pub weight: f64,
    pub characteristics: Vec<CharacteristicInput>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RubricInput {
    pub rubric_id: String,
    pub scope: String,
    pub name: String,
    pub version: i32,
    pub description: Option<String>,
    pub groups: Vec<GroupInput>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CharacteristicScoreInput {
    pub characteristic_id: String,
    pub score: i32,
    pub rationale: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RubricScoreRequest {
    pub rubric: RubricInput,
    pub target_id: String,
    pub scores: Vec<CharacteristicScoreInput>,
    pub pass_threshold_pct: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RubricScoreReport {
    pub rubric_id: String,
    pub target_id: String,
    pub scores: Vec<CharacteristicScoreInput>,
    pub weighted_total: f64,
    pub normalized_pct: f64,
    pub passed: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "command", content = "input", rename_all = "snake_case")]
pub enum StrataRequest {
    ComputeRubricScore(RubricScoreRequest),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "kind", content = "value", rename_all = "snake_case")]
pub enum StrataResponse {
    RubricScoreReport(RubricScoreReport),
}

pub fn handle_request(request: StrataRequest) -> StrataResponse {
    match request {
        StrataRequest::ComputeRubricScore(request) => {
            StrataResponse::RubricScoreReport(compute_rubric_score(request))
        }
    }
}

pub fn compute_rubric_score(request: RubricScoreRequest) -> RubricScoreReport {
    let score_by_id = request
        .scores
        .iter()
        .map(|s| (s.characteristic_id.as_str(), s.score))
        .collect::<std::collections::HashMap<_, _>>();

    let mut weighted = 0.0;
    for group in &request.rubric.groups {
        for character in &group.characteristics {
            let score = score_by_id
                .get(character.id.as_str())
                .copied()
                .unwrap_or_else(|| panic!("missing score for characteristic '{}'", character.id));
            weighted += group.weight * character.weight * score as f64;
        }
    }

    let max_score = request
        .rubric
        .groups
        .first()
        .and_then(|group| group.characteristics.first())
        .and_then(|character| character.attributes.iter().map(|a| a.score).max())
        .unwrap_or(4)
        .max(1) as f64;

    let normalized = (weighted / max_score) * 100.0;
    RubricScoreReport {
        rubric_id: request.rubric.rubric_id,
        target_id: request.target_id,
        scores: request.scores,
        weighted_total: weighted,
        normalized_pct: normalized,
        passed: normalized >= request.pass_threshold_pct,
    }
}
