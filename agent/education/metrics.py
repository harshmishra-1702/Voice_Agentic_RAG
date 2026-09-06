from typing import List, Dict, Any

def compute_metrics(retrieval_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not retrieval_results:
        return {"mean_recall": 0.0, "latest_recall": 0.0, "earliest_recall": 0.0}
    
    scores = [r["score"] for r in retrieval_results]
    return {
        "mean_recall": sum(scores) / len(scores),
        "latest_recall": scores[-1] if scores else 0.0,
        "earliest_recall": scores[0] if scores else 0.0
    }
