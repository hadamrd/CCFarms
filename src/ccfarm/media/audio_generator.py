import os
from typing import Iterator
from elevenlabs.client import ElevenLabs
import io
from pydub import AudioSegment

class VoiceActor:
    ACTOR_VOICE_ID = "zGjIP4SZlMnY9m93k97r"
    
    def __init__(self, api_key):
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("ElevenLabs API key required")
        
        self.client = ElevenLabs(api_key=api_key)
    
    def generate_segment_audio(self, segment_text) -> Iterator[bytes]:
        return self.client.text_to_speech.convert(text=segment_text, voice_id=self.ACTOR_VOICE_ID)
    
    def convert_audio_to_bytes(self, audio_generator) -> bytes:
        audio_bytes = b"".join(chunk for chunk in audio_generator)
        return audio_bytes
    
    def convert_bytes_to_audio(self, audio_bytes) -> AudioSegment:
        return AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
    
    def save_audio(self, audio_segment, output_path, format="mp3"):
        audio_segment.export(output_path, format=format)

    def from_text(self, text: str) -> AudioSegment:
        audio_generator = self.generate_segment_audio(text)
        audio_bytes = self.convert_audio_to_bytes(audio_generator)
        return self.convert_bytes_to_audio(audio_bytes)
