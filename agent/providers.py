import os

class SpeechToTextProvider:
    def get_plugin(self):
        raise NotImplementedError

class DeepgramSTTAdapter(SpeechToTextProvider):
    def get_plugin(self):
        from livekit.plugins import deepgram
        return deepgram.STT(
            model="nova-3",
            language="en",
            punctuate=True,
            smart_format=True,
        )

class WhisperSTTAdapter(SpeechToTextProvider):
    def get_plugin(self):
        from livekit.plugins import openai
        return openai.STT(
            model="whisper-1",
            base_url=os.environ.get("WHISPER_URL", "http://localhost:11434/v1")
        )

class LanguageModelProvider:
    def get_plugin(self):
        raise NotImplementedError

class GroqLLMAdapter(LanguageModelProvider):
    def get_plugin(self):
        from livekit.plugins import openai
        return openai.LLM(
            model="openai/gpt-oss-20b",
            base_url="https://api.groq.com/openai/v1",
            api_key=os.environ.get("GROQ_API_KEY", ""),
            temperature=0.6,
        )

class OllamaLLMAdapter(LanguageModelProvider):
    def get_plugin(self):
        from livekit.plugins import openai
        return openai.LLM(
            model=os.environ.get("OLLAMA_MODEL", "llama3"),
            base_url=os.environ.get("OLLAMA_URL", "http://localhost:11434/v1"),
            api_key="ollama"
        )

class TextToSpeechProvider:
    def get_plugin(self):
        raise NotImplementedError

class RimeTTSAdapter(TextToSpeechProvider):
    def get_plugin(self):
        from livekit.plugins import rime
        return rime.TTS(
            model="coda",
            speaker="astra",
            use_websocket=True,
        )

class PiperTTSAdapter(TextToSpeechProvider):
    def get_plugin(self):
        # Using openai TTS as fallback for local server providing piper
        from livekit.plugins import openai
        return openai.TTS(
            model="piper",
            base_url=os.environ.get("PIPER_URL", "http://localhost:5000/v1")
        )

def get_stt_adapter() -> SpeechToTextProvider:
    provider = os.environ.get("STT_PROVIDER", "deepgram").lower()
    if provider == "whisper":
        return WhisperSTTAdapter()
    return DeepgramSTTAdapter()

def get_llm_adapter() -> LanguageModelProvider:
    provider = os.environ.get("LLM_PROVIDER", "groq").lower()
    if provider == "ollama":
        return OllamaLLMAdapter()
    return GroqLLMAdapter()

def get_tts_adapter() -> TextToSpeechProvider:
    provider = os.environ.get("TTS_PROVIDER", "rime").lower()
    if provider == "piper":
        return PiperTTSAdapter()
    return RimeTTSAdapter()
