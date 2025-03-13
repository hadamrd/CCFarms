import os
from ccfarm.agents.satirist.models import ComedyScript
from dotenv import load_dotenv
from moviepy import concatenate_videoclips

script_json_1 = {
    "title": "Siri's Mid-Life Crisis: Apple's AI Assistant Still Can't Remember Your Name",
    "description": "A satirical look at Apple's latest admission that their AI assistant Siri needs more time in digital therapy before it can master basic conversation skills, like remembering who you are.",
    "topic_tags": ["Technology", "AI", "Apple", "Siri", "Product Delays"],
    "segments": [
        {
            "text": '<prosody rate="90%" pitch="-10%">Breaking news: Apple\'s virtual assistant Siri is apparently having an identity crisis. The company admits their AI needs <emphasis level="strong">even more time</emphasis> to figure out how to remember your name.</prosody> <break time="1s"/> Which is totally not concerning at all.',
            "keywords": [
                "siri-confused",
                "robot-malfunction",
                "ai-failure",
                "apple-logo",
                "virtual-assistant",
                "tech-fail",
            ],
        },
        {
            "text": '<prosody rate="95%">While ChatGPT is writing shakespearean sonnets, <emphasis level="strong">poor Siri</emphasis> is still struggling to master the complex task of... checking your calendar.</prosody> <break time="0.5s"/> <prosody pitch="+15%">But hey, at least it can tell you the weather!</prosody>',
            "keywords": [
                "calendar-fail",
                "siri-confused",
                "chatgpt",
                "robot-facepalm",
                "tech-struggle",
                "weather-app",
            ],
        },
        {
            "text": '<prosody rate="85%">Apple\'s spokesperson assured us these features will arrive "in the coming year" - which in Apple time could mean anywhere between next week and the heat death of the universe.</prosody> <break time="1s"/> <emphasis level="strong">Until then, maybe try writing things down with a pencil?</emphasis>',
            "keywords": [
                "waiting-forever",
                "apple-logo",
                "hourglass",
                "tech-delay",
                "pencil-paper",
                "frustrated-user",
            ],
        },
    ],
}


scripts = [ComedyScript.model_validate(script_json_1)]


def convert_multiple_scripts_to_video(
    scripts: list[ComedyScript],  # List of ComedyScript objects
    elevenlabs_api_key: str,
    giphy_api_key: str,
    output_path: str = "output.mp4",
    frame_size=(1280, 720),
    codec="libx264",
    audio_codec="libmp3lame",
    fps=24,
    audio_bitrate="192k",
):
    if not scripts:
        print("No scripts provided to convert")
        return None

    print(f"Processing {len(scripts)} comedy scripts")

    # Process each script to generate a video clip
    all_video_clips = []

    for i, script in enumerate(scripts):
        print(f"Processing script {i+1}/{len(scripts)}: {script.title}")

        # Generate video for this script (but don't write to file yet)
        script_clip = script.convert_to_video(
            elevenlabs_api_key=elevenlabs_api_key,
            giphy_api_key=giphy_api_key,
            output_path=None,  # Don't export individual scripts
            frame_size=frame_size,
        )

        if script_clip:
            all_video_clips.append(script_clip)
            print(f"Successfully processed script {i+1}")
        else:
            print(f"Failed to create video for script {i+1}: {script.title}")

    # If no clips were successfully created, exit
    if not all_video_clips:
        print("No script videos were successfully created")
        return None

    try:
        # Concatenate all script clips
        print(f"Concatenating {len(all_video_clips)} script videos")
        final_video = concatenate_videoclips(all_video_clips)

        # Export final video
        print(f"Writing final video to {output_path}")
        final_video.write_videofile(
            output_path, codec=codec, audio_codec=audio_codec, fps=fps, audio_bitrate=audio_bitrate
        )

        print(f"Multiple scripts video created successfully: {output_path}")
        return output_path
    except Exception as e:
        print(f"Error creating combined video: {str(e)}")
        return None


load_dotenv()
eleven_labs_api_key = os.getenv("ELEVENLABS_API_KEY")
giphy_api_key = os.getenv("GIPHY_API_KEY")

if not eleven_labs_api_key or not giphy_api_key:
    raise ValueError("ElevenLabs and GIPHY API keys are required")

convert_multiple_scripts_to_video(
    scripts, eleven_labs_api_key, giphy_api_key, output_path="combined_output.mp4"
)
