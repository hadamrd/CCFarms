import boto3
from pathlib import Path
import tempfile
from typing import Dict, List, Optional
import re

class PollyVoiceGenerator:
    """Voice generator using Amazon Polly with SSML support for comedy emphasis."""
    
    # Mapping of tones to Polly voices
    TONE_VOICE_MAPPING = {
        "neutral": "Matthew",      # Balanced, professional
        "upbeat": "Joanna",        # Energetic, cheerful
        "excited": "Nicole",       # High energy, animated
        "serious": "Brian",        # Deep, authoritative
        "sarcastic": "Kendra",     # Good for deadpan delivery
        "funny": "Joey",           # Expressive, versatile
        "deadpan": "Kevin",        # Flat affect, good for dry humor
        "amused": "Ruth",          # Warm, slightly playful
        "warm": "Salli"            # Friendly, inviting
    }
    
    NEURAL_VOICES = ["Matthew", "Joanna", "Kendra", "Kevin", "Joey"]
    
    # Default voice if tone isn't found
    DEFAULT_VOICE = "Matthew"
    
    def __init__(self, boto3_client=None, aws_access_key=None, aws_secret_key=None, region_name="us-east-1", output_dir=None):
        """Initialize the Polly voice generator."""
        if boto3_client is not None:
            self.polly_client = boto3_client
        else:
            # Check if credentials are provided
            if aws_access_key and aws_secret_key:
                # Create client with provided credentials
                self.polly_client = boto3.client(
                    'polly',
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                    region_name=region_name
                )
            else:
                # Use environment or default AWS credentials
                self.polly_client = boto3.client('polly', region_name=region_name)
        
        # Set up output directory
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path(tempfile.gettempdir()) / "voice_segments"
        
        self.output_dir.mkdir(exist_ok=True, parents=True)
    
    def process_script(self, script: dict, max_segments: Optional[int] = None) -> Optional[str]:
        """Process a script JSON and generate audio for segments."""
        try:
            
            # Extract segments
            segments = script.get("segments", [])
            
            # Limit segments if specified
            if max_segments is not None:
                segments = segments[:max_segments]
            
            # Generate audio for each segment
            audio_files = []
            for i, segment in enumerate(segments):
                print(f"Processing segment {i+1}/{len(segments)}")
                audio_path = self.generate_segment_audio(segment, i)
                if audio_path:
                    audio_files.append(audio_path)
            
            # Combine segments
            if audio_files:
                return self.combine_audio_segments(audio_files)
            
            return None
            
        except Exception as e:
            print(f"Error processing script: {str(e)}")
            return None
    
    def generate_segment_audio(self, segment: Dict, index: int) -> Optional[str]:
        """Generate audio for a single segment using Polly with SSML."""
        try:
            # Extract parameters
            text = segment.get("text", "")
            tone = segment.get("voice_tone", segment.get("tone", "neutral"))
            pause_after = segment.get("pause_after", 0.0)
            
            if not text:
                return self._create_silence_file(1.0, index)
            
            # Select voice based on tone
            voice_id = self.TONE_VOICE_MAPPING.get(tone.lower(), self.DEFAULT_VOICE)
            
            # Properly sanitize and prepare SSML text
            text = self._prepare_ssml(text, voice_id)
            
            # Log the query for debugging
            print(f"Generating segment {index} with voice: {voice_id}")
            print(f"Text: {text}")
            
            response = self.polly_client.synthesize_speech(
                Engine='neural',
                OutputFormat='mp3',
                Text=text,
                TextType='ssml',
                VoiceId=voice_id
            )
            
            # Save audio to file
            if "AudioStream" in response:
                output_file = str(self.output_dir / f"segment_{index:03d}.mp3")
                with open(output_file, "wb") as file:
                    file.write(response["AudioStream"].read())
                
                # Add pause if needed
                if pause_after > 0:
                    return self._add_pause_after(output_file, pause_after, index)
                
                return output_file
            
            return None
            
        except Exception as e:
            print(f"Error generating segment {index}: {str(e)}")
            return None
    
    def _prepare_ssml(self, text: str, voice_id: str) -> str:
        """Prepare and fix SSML text for Amazon Polly."""
        # Remove any existing speak tags
        text = re.sub(r'</?speak>', '', text)
        
        # Fix common SSML issues
        # 1. Close unclosed prosody tags
        open_prosody = text.count('<prosody')
        close_prosody = text.count('</prosody')
        if open_prosody > close_prosody:
            for _ in range(open_prosody - close_prosody):
                text = text + '</prosody>'
        
        # 2. Close unclosed emphasis tags
        open_emphasis = text.count('<emphasis')
        close_emphasis = text.count('</emphasis')
        if open_emphasis > close_emphasis:
            for _ in range(open_emphasis - close_emphasis):
                text = text + '</emphasis>'
                
        # Apply neural voice limitations if needed
        if voice_id in self.NEURAL_VOICES:
            # 3. Keep pitch modifications within neural voice limits (+/- 20%)
            text = re.sub(r'pitch=[\'"]([+-])(\d{2,})[\'"%]', lambda m: f'pitch="{m.group(1)}20%"' if int(m.group(2)) > 20 else m.group(0), text)
            
            # 4. Remove unsupported SSML tags for neural voices
            text = re.sub(r'<say-as[^>]*>.*?</say-as>', '', text)
            
        # Wrap the final text in speak tags
        return f"<speak>{text}</speak>"
    
    def _sanitize_ssml_for_neural(self, ssml: str) -> str:
        """Clean SSML for Neural voice compatibility"""
        # This method is replaced by the more comprehensive _prepare_ssml
        return ssml
    
    def _create_silence_file(self, duration: float, index: int) -> str:
        """Create a silent audio file of specified duration."""
        from pydub import AudioSegment
        
        silence = AudioSegment.silent(duration=int(duration * 1000))
        
        silence_file = str(self.output_dir / f"silence_{index:03d}.mp3")
        silence.export(silence_file, format="mp3")
        
        return silence_file
    
    def _add_pause_after(self, audio_path: str, pause_duration: float, index: int) -> str:
        """Add a pause after the audio segment."""
        from pydub import AudioSegment
        
        try:
            # Load audio
            audio = AudioSegment.from_file(audio_path)
            
            # Create silence
            silence = AudioSegment.silent(duration=int(pause_duration * 1000))
            
            # Combine
            combined = audio + silence
            
            # Save
            output_file = str(self.output_dir / f"segment_with_pause_{index:03d}.mp3")
            combined.export(output_file, format="mp3")
            
            return output_file
            
        except Exception as e:
            print(f"Error adding pause: {str(e)}")
            return audio_path
    
    def combine_audio_segments(self, segment_files: List[str]) -> str:
        """Combine multiple audio segments into a single file."""
        from pydub import AudioSegment
        
        try:
            if not segment_files:
                return None
            
            # Start with first segment
            combined = AudioSegment.from_file(segment_files[0])
            
            # Add the rest
            for file_path in segment_files[1:]:
                segment = AudioSegment.from_file(file_path)
                combined += segment
            
            # Save the combined audio
            timestamp = tempfile._get_candidate_names().__next__()
            output_file = str(self.output_dir / f"combined_output_{timestamp}.mp3")
            combined.export(output_file, format="mp3")
            
            return output_file
            
        except Exception as e:
            print(f"Error combining segments: {str(e)}")
            return None