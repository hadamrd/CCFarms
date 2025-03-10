import os
import io
import tempfile
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel
from prefect import get_run_logger
from tenacity import retry, stop_after_attempt, wait_random_exponential

import requests
from openai import OpenAI
import soundfile as sf
import numpy as np
from pydub import AudioSegment

from ccfarm.agents.base_agent import BaseAgent


class VoiceGenerationError(Exception):
    """Exception raised when voice generation fails."""
    pass


class VoiceGenerator(BaseAgent):
    """
    AI agent that generates voice audio from comedy script segments.
    Uses OpenAI's TTS API for high-quality, cost-effective voice generation.
    """
    
    # Voice options mapping (for OpenAI TTS)
    VOICE_TONE_MAPPING = {
        "neutral": "shimmer",  # Balanced, versatile voice
        "excited": "alloy",    # Energetic, younger-sounding voice
        "serious": "onyx",     # Deeper, authoritative voice
        "funny": "nova",       # Friendly, expressive voice
        "sarcastic": "echo",   # Slightly lower, good for sarcasm
    }
    
    # Default voice if tone isn't found in mapping
    DEFAULT_VOICE = "shimmer"
    
    def __init__(
        self,
        openai_api_key: str,
    ):
        # Set up the directory for this agent
        self.agent_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Configure LLM settings for AutoGen (used minimally for voice settings)
        llm_config = {
            "config_list": [
                {
                    "model": "gpt-4-turbo",
                    "api_key": openai_api_key,
                }
            ],
            "temperature": 0.2,  # Lower temperature for more predictable outputs
        }
        
        super().__init__(
            name="VoiceGenerator",
            llm_config=llm_config,
            template_dir=self.agent_dir,
        )
        
        self.logger = get_run_logger()
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.output_dir = Path(tempfile.gettempdir()) / "voice_segments"
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
    def generate_voice_for_script(self, script: Dict) -> str:
        """
        Generate voice audio for an entire comedy script.
        
        Args:
            script: Dictionary with script data (same format as from Satirist agent)
            
        Returns:
            Path to the final combined audio file
        """
        self.logger.info(f"Generating voice for script: {script.get('script_data', {}).get('title', 'Untitled')}")
        
        try:
            script_data = script.get("script_data", {})
            segments = script_data.get("segments", [])
            
            if not segments:
                raise VoiceGenerationError("No segments found in script data")
            
            # Generate voice for each segment
            segment_files = []
            for i, segment in enumerate(segments):
                self.logger.info(f"Processing segment {i+1}/{len(segments)}")
                segment_path = self.generate_voice_for_segment(
                    segment=segment,
                    index=i,
                    script_id=script.get("script_id", datetime.now().strftime("%Y%m%d%H%M%S"))
                )
                segment_files.append(segment_path)
            
            # Combine all segments into a single file
            final_path = self.combine_audio_segments(
                segment_files=segment_files,
                script_id=script.get("script_id", datetime.now().strftime("%Y%m%d%H%M%S"))
            )
            
            self.logger.info(f"Successfully generated voice for script: {final_path}")
            return final_path
            
        except Exception as e:
            self.logger.error(f"Error generating voice for script: {str(e)}")
            raise VoiceGenerationError(f"Failed to generate voice: {str(e)}") from e
    
    @retry(stop=stop_after_attempt(3), wait=wait_random_exponential(multiplier=1, max=20))
    def generate_voice_for_segment(self, segment: Dict, index: int, script_id: str) -> str:
        """
        Generate voice audio for a single segment using OpenAI's TTS API.
        
        Args:
            segment: Dictionary with segment data (text, tone, speed, pause_after)
            index: Segment index for file naming
            script_id: Script identifier for file naming
            
        Returns:
            Path to the generated audio file
        """
        self.logger.info(f"Generating voice for segment {index+1}")
        
        # Extract segment parameters
        text = segment.get("text", "")
        tone = segment.get("tone", "neutral")
        speed = segment.get("speed", 1.0)
        pause_after = segment.get("pause_after", 0.0)
        
        if not text:
            self.logger.warning(f"Empty text for segment {index+1}")
            return self._create_silence_file(1.0, index, script_id)  # Return 1 second of silence
        
        try:
            # Determine the voice based on tone
            voice = self.VOICE_TONE_MAPPING.get(tone.lower(), self.DEFAULT_VOICE)
            
            # Generate speech with OpenAI TTS
            response = self.openai_client.audio.speech.create(
                model="tts-1",  # Use tts-1 for cost-effectiveness, or tts-1-hd for higher quality
                voice=voice,
                input=text,
                speed=speed
            )
            
            # Save to temporary file
            segment_filename = f"{script_id}_segment_{index:03d}.mp3"
            segment_path = self.output_dir / segment_filename
            
            # Save the audio content
            with open(segment_path, "wb") as f:
                response.stream_to_file(segment_path)
            
            # Add pause if specified
            if pause_after > 0:
                segment_path = self._add_pause_after(segment_path, pause_after, index, script_id)
            
            self.logger.info(f"Voice generated for segment {index+1}: {segment_path}")
            return str(segment_path)
            
        except Exception as e:
            self.logger.error(f"Error generating voice for segment {index+1}: {str(e)}")
            raise VoiceGenerationError(f"Failed to generate voice for segment {index+1}: {str(e)}") from e
    
    def _create_silence_file(self, duration: float, index: int, script_id: str) -> str:
        """Create a silence audio file of specified duration."""
        # Create a silent audio segment
        silence = AudioSegment.silent(duration=int(duration * 1000))  # Duration in milliseconds
        
        # Save to file
        silence_filename = f"{script_id}_silence_{index:03d}.mp3"
        silence_path = self.output_dir / silence_filename
        silence.export(silence_path, format="mp3")
        
        return str(silence_path)
    
    def _add_pause_after(self, audio_path: Path, pause_duration: float, 
                         index: int, script_id: str) -> str:
        """Add a pause (silence) after the audio segment."""
        try:
            # Load the audio file
            audio = AudioSegment.from_file(audio_path)
            
            # Create silence of specified duration
            silence = AudioSegment.silent(duration=int(pause_duration * 1000))  # Convert to milliseconds
            
            # Combine audio with silence
            combined = audio + silence
            
            # Save to a new file
            combined_filename = f"{script_id}_segment_with_pause_{index:03d}.mp3"
            combined_path = self.output_dir / combined_filename
            combined.export(combined_path, format="mp3")
            
            return str(combined_path)
            
        except Exception as e:
            self.logger.error(f"Error adding pause to segment {index}: {str(e)}")
            # Return original path if pause addition fails
            return str(audio_path)
    
    def combine_audio_segments(self, segment_files: List[str], script_id: str) -> str:
        """Combine multiple audio segments into a single file."""
        self.logger.info(f"Combining {len(segment_files)} audio segments")
        
        try:
            if not segment_files:
                raise VoiceGenerationError("No segment files to combine")
            
            # Initialize with the first segment
            combined = AudioSegment.from_file(segment_files[0])
            
            # Add the rest of the segments
            for segment_path in segment_files[1:]:
                segment = AudioSegment.from_file(segment_path)
                combined += segment
            
            # Save the combined audio
            output_filename = f"{script_id}_combined.mp3"
            output_path = self.output_dir / output_filename
            combined.export(output_path, format="mp3")
            
            self.logger.info(f"Successfully combined audio segments: {output_path}")
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"Error combining audio segments: {str(e)}")
            raise VoiceGenerationError(f"Failed to combine audio segments: {str(e)}") from e
        
    def clean_up_segment_files(self, segment_files: List[str]) -> None:
        """Remove temporary segment files to free up space."""
        for file_path in segment_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                self.logger.warning(f"Failed to remove temporary file {file_path}: {str(e)}")
