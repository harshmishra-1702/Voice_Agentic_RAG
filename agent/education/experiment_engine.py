from typing import List, Dict, Any, Optional
import uuid
from .memory_model import EducationalMemoryModel
from .metrics import compute_metrics

def run_experiment(sequence: List[str], memory_size: int, update_strength: float, interference: float, seed: int, retrieval_targets: Optional[List[str]] = None) -> Dict[str, Any]:
    model = EducationalMemoryModel(memory_size, update_strength, interference, seed)
    
    steps = []
    for t, item in enumerate(sequence):
        state = model.step(item)
        steps.append({
            "t": t,
            "input": item,
            "state": state.tolist()
        })
        
    targets = retrieval_targets if retrieval_targets is not None else sequence
    retrieval = []
    for target in targets:
        score = model.retrieve(target)
        expected = target in sequence
        # We consider recovered if score > threshold
        recovered = score > 0.5
        retrieval.append({
            "target": target,
            "expected": expected,
            "score": score,
            "recovered": recovered
        })
        
    metrics = compute_metrics(retrieval)
    
    return {
        "experiment_id": f"exp-{uuid.uuid4().hex[:8]}",
        "parameters": {
            "memory_size": memory_size,
            "update_strength": update_strength,
            "interference": interference,
            "seed": seed
        },
        "steps": steps,
        "retrieval": retrieval,
        "metrics": metrics,
        "model_type": "educational_toy_recurrent_memory",
        "official_bdh": False
    }
