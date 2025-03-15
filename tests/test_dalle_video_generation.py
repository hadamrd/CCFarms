from ccfarm.agents.satirist.models import VideoScript, SpeechSegment
from ccfarm.media.dalle_video_gen import DalleVideoGenerator
from prefect.blocks.system import Secret

# Example script with a single segment
script = VideoScript(
    title="AI Journalism: Because Real Journalists Need Jobs Too",
    description="A satirical take on an AI news system falsely accusing a Yale scholar of terrorism.",
    tags=["AI", "Technology", "Academia", "Journalism", "Ethics"],
    segments=[
        SpeechSegment(
            text="First up, an <emphasis level=\"strong\">AI-EMPOWERED</emphasis> news site accused a Yale scholar of terrorism, causing her suspension! <break time=\"0.7s\"/> Because nothing says \"trusted journalism\" like having an algorithm that probably can't tell the difference between Hamas and hummus making career-ending accusations. <prosody rate=\"115%\">I'm sure the AI was trained on such reliable data sources as 'Twitter comments section' and 'My uncle's Facebook rants.'</prosody>",
            keywords=["AI journalism", "Yale scholar", "algorithm failure", "hummus joke", "social media"]
        )
    ]
)

# API keys
anthropic_api_key = Secret.load("anthropic-api-key").get()
news_api_key = Secret.load("news-api-key").get()
elevenlabs_api_key = Secret.load("elevenlabs-api-key").get()
openai_api_key = Secret.load("openai-api-key").get()

# Generate video
output_path = "satirical_news_segment.mp4"
script.convert_to_video_dalle(
    elevenlabs_api_key=elevenlabs_api_key,
    anthropic_api_key=anthropic_api_key,
    openai_api_key=openai_api_key,
    output_path=output_path
)

print(f"Video created at: {output_path}")


# Alternative: Process a single segment directly
def process_single_segment():
    segment = SpeechSegment(
        text="First up, an <emphasis level=\"strong\">AI-EMPOWERED</emphasis> news site accused a Yale scholar of terrorism, causing her suspension! <break time=\"0.7s\"/> Because nothing says \"trusted journalism\" like having an algorithm that probably can't tell the difference between Hamas and hummus making career-ending accusations.",
        keywords=["AI journalism", "Yale scholar", "algorithm failure", "hummus joke"]
    )
    
    # Initialize the enhanced video generator
    video_generator = DalleVideoGenerator(
        frame_size=(1280, 720),
        anthropic_api_key=anthropic_api_key,
        openai_api_key=openai_api_key
    )
    
    # Create an audio generator
    from ccfarm.media.audio_generator import VoiceActor
    audio_generator = VoiceActor(api_key=elevenlabs_api_key)
    
    # Generate audio
    audio_segment = audio_generator.from_text(segment.text)
    
    # Generate video
    final_video = video_generator.from_text(
        text=segment.text,
        audio=audio_segment,
        output_path="single_segment.mp4"
    )
    
    print("Single segment video created!")

# Uncomment to run the single segment example
# process_single_segment()