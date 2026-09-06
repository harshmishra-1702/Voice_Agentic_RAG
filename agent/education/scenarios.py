from .experiment_engine import run_experiment

def run_short_sequence():
    return run_experiment(sequence=["A", "B", "C", "D"], memory_size=8, update_strength=0.6, interference=0.1, seed=42)

def run_long_sequence():
    return run_experiment(sequence=["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"], memory_size=8, update_strength=0.6, interference=0.1, seed=42)

def run_interference():
    return run_experiment(sequence=["A", "B", "A", "C", "A", "D"], memory_size=8, update_strength=0.6, interference=0.5, seed=42)

def run_forgetting():
    return run_experiment(sequence=["A", "B", "C", "D", "E"], memory_size=8, update_strength=0.6, interference=0.8, seed=42)
