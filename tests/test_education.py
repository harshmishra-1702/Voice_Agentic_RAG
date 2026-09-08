import pytest
from agent.education.memory_model import EducationalMemoryModel
from agent.education.experiment_engine import run_experiment
from agent.education import scenarios

def test_memory_model_deterministic():
    model1 = EducationalMemoryModel(memory_size=4, update_strength=0.5, interference=0.1, seed=42)
    state1 = model1.step("A")
    
    model2 = EducationalMemoryModel(memory_size=4, update_strength=0.5, interference=0.1, seed=42)
    state2 = model2.step("A")
    
    assert (state1 == state2).all()
    assert model1.retrieve("A") == model2.retrieve("A")

def test_memory_model_state_shape():
    model = EducationalMemoryModel(memory_size=10, update_strength=0.6, interference=0.1, seed=42)
    state = model.step("B")
    assert state.shape == (10,)

def test_experiment_engine_basic():
    result = run_experiment(sequence=["X", "Y"], memory_size=4, update_strength=0.5, interference=0.0, seed=1)
    
    assert "experiment_id" in result
    assert result["parameters"]["memory_size"] == 4
    assert len(result["steps"]) == 2
    assert result["steps"][0]["input"] == "X"
    assert result["steps"][1]["input"] == "Y"
    
    assert len(result["retrieval"]) == 2
    assert result["retrieval"][0]["target"] == "X"
    
    metrics = result["metrics"]
    assert "mean_recall" in metrics
    assert "latest_recall" in metrics
    assert "earliest_recall" in metrics

def test_scenarios_run():
    short_res = scenarios.run_short_sequence()
    assert len(short_res["steps"]) == 4
    
    long_res = scenarios.run_long_sequence()
    assert len(long_res["steps"]) == 12
    
    interference_res = scenarios.run_interference()
    assert len(interference_res["steps"]) == 6
    
    forget_res = scenarios.run_forgetting()
    assert len(forget_res["steps"]) == 5
