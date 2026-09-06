import numpy as np

class EducationalMemoryModel:
    def __init__(self, memory_size: int, update_strength: float, interference: float, seed: int):
        self.memory_size = memory_size
        self.alpha = update_strength
        self.beta = interference
        self.rng = np.random.default_rng(seed)
        self.state = np.zeros(memory_size)
        self.vocab_embeddings = {}

    def _encode(self, item: str) -> np.ndarray:
        if item not in self.vocab_embeddings:
            # Generate deterministic random vector for this item
            vec = self.rng.standard_normal(self.memory_size)
            self.vocab_embeddings[item] = self._normalize(vec)
        return self.vocab_embeddings[item]

    def _normalize(self, vec: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vec)
        if norm < 1e-9:
            return vec
        return vec / norm

    def step(self, item: str):
        encoded = self._encode(item)
        noise = self.rng.standard_normal(self.memory_size)
        noise = self._normalize(noise)
        
        self.state = self._normalize(
            (1 - self.alpha) * self.state + 
            self.alpha * encoded + 
            self.beta * noise
        )
        return self.state.copy()

    def retrieve(self, item: str) -> float:
        encoded = self._encode(item)
        # Cosine similarity
        score = np.dot(encoded, self.state)
        # Bounded between -1 and 1 due to normalized vectors
        return float(score)
