import os
import json
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
import io
from pydub import AudioSegment

# Load environment variables
load_dotenv()

# Initialize ElevenLabs client
client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

def load_script_from_json(filepath):
    """Load script from a JSON file."""
    with open(filepath, "r") as f:
        return json.load(f) 

def generate_audio_from_script(script_json, output_dir="output"):
    """Generate audio from a JSON script and create metadata."""
    os.makedirs(output_dir, exist_ok=True)
    audio_clips = []

    # Voice ID for ElevenLabs
    voice_id = "zGjIP4SZlMnY9m93k97r"  # Podcaster voice
    title = script_json["title"]

    # Generate audio for each segment
    for i, segment in enumerate(script_json["segments"]):
        text = segment["text"]
        character = segment.get("character", "Podcaster")
        tone = segment.get("tone", "neutral")
        keywords = segment.get("keywords", [])

        print(f"Generating audio for segment {i+1}: {character}")

        # Generate audio using ElevenLabs
        audio_generator = client.text_to_speech.convert(text=text, voice_id=voice_id)
        audio_bytes = b"".join(chunk for chunk in audio_generator)

        # Save audio clip
        clip_path = os.path.join(output_dir, f"{i+1:02d}_{character}.mp3")
        with open(clip_path, "wb") as f:
            f.write(audio_bytes)

        # Calculate duration
        audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
        duration = len(audio_segment) / 1000.0  # Duration in seconds

        # Store metadata
        audio_clips.append({
            "text": text,
            "character": character,
            "tone": tone,
            "filename": os.path.basename(clip_path),
            "duration": duration,
            "keywords": keywords,
        })

    # Combine audio clips using pydub
    if audio_clips:
        combined_audio_segment = AudioSegment.empty()
        for clip in audio_clips:
            clip_path = os.path.join(output_dir, clip["filename"])
            audio_segment = AudioSegment.from_file(clip_path, format="mp3")
            combined_audio_segment += audio_segment
        
        combined_filename = f"{title.replace(' ', '_')}_combined.mp3"
        combined_path = os.path.join(output_dir, combined_filename)
        combined_audio_segment.export(combined_path, format="mp3")
        print(f"\nCombined audio saved to {combined_path}")

        # Create metadata file
        metadata = {
            "title": title,
            "description": script_json.get("description", ""),
            "source": script_json.get("news_source", ""),
            "segments": audio_clips,
            "combined_file": combined_filename,
        }
        metadata_path = os.path.join(output_dir, f"{title.replace(' ', '_')}_metadata.json")
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        print(f"Metadata saved to {metadata_path}")
        
        return metadata_path

def main():
    # Check if script file was provided as argument
    import sys
    if len(sys.argv) > 1:
        script_path = sys.argv[1]
        script_json = load_script_from_json(script_path)
    else:
        # Use sample script if no file provided
        script_json = {
            "title": "Netflix's AI Upgrade Turns 80s Sitcom into Digital Horror Show",
            "description": "A satirical look at Netflix's disastrous attempt to use AI...",
            "segments": [
                {
                    "text": '<prosody rate="90%" pitch="-10%">In Netflix\'s latest attempt to prove that AI can do everything better than humans, they\'ve successfully transformed \'A Different World\' into what can only be described as \'A HORRIFYING World.\'</prosody> <break time="0.5s"/> <emphasis level="strong">Congratulations on inventing digital body horror!</emphasis>',
                    "keywords": ["facepalm", "horrified", "sarcastic", "tech-fail"],
                },
                {
                    "text": '<prosody rate="110%">The AI apparently went to the Salvador Dali school of image processing, giving characters extra fingers, melted faces, and text that looks like it was written by a cat walking across a keyboard.</prosody> <break time="0.5s"/> <emphasis level="strong">It\'s not a bug, it\'s a FEATURE!</emphasis>',
                    "keywords": ["glitch", "confused", "eye-roll", "bizarre"],
                },
                {
                    "text": '<prosody pitch="+15%">Netflix\'s cost-cutting solution has given us something truly special - the world\'s first sitcom that doubles as a psychological horror experiment!</prosody> <break time="1s"/> <emphasis level="strong">Who needs actual remastering when you can traumatize your audience for free?</emphasis>',
                    "keywords": ["laughing", "scared", "mocking", "cringe"],
                },
            ],
        }
    
    generate_audio_from_script(script_json)

if __name__ == "__main__":
    main()