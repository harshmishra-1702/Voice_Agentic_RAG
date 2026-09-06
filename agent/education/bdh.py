from typing import Dict, Any, Optional

# A static dictionary for now to satisfy the BDH module requirement
# In a full implementation, this could query the RAG system or a dedicated DB
_EVIDENCE_DB = {
    "recurrent_memory": {
        "concept": "recurrent_memory",
        "claim": "A fixed-size recurrent state can process sequences of unbounded duration, but limited state capacity and interference can make earlier information less recoverable.",
        "system": "BDH",
        "evidence_level": "primary_source",
        "source_type": "paper",
        "source_title": "Understanding Recurrent Memory Models",
        "what_changes": "State updates incrementally without expanding.",
        "what_is_not_claimed": "Perfect infinite memory without forgetting."
    }
}

def get_bdh_explanation(concept: str) -> str:
    data = _EVIDENCE_DB.get(concept)
    if not data:
        return "I don't have enough source evidence to explain that concept."
    return f"In {data['system']}, {data['claim']}"

def get_bdh_comparison(concept: str) -> Dict[str, Any]:
    data = _EVIDENCE_DB.get(concept)
    if not data:
        return {}
    
    return {
        "concept": concept,
        "toy_model_aspect": "Simplified deterministic mathematical update.",
        "bdh_aspect": "Published architecture with learned weights.",
        "official": data["source_type"] == "official_material"
    }

def get_bdh_evidence(concept: str) -> Optional[Dict[str, Any]]:
    return _EVIDENCE_DB.get(concept)
