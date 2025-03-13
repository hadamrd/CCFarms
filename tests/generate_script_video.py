import os
from ccfarm.agents.satirist.models import ComedyScript
from dotenv import load_dotenv
from moviepy import concatenate_videoclips

script_json_1 ={
    "title": "Russian Trolls Discover One Weird Trick to Hack AI: Just Keep Typing!",
    "description": "A satirical take on Russia's hilariously obvious attempt to spam AI systems with propaganda, proving that sometimes the best hacking technique is just overwhelming your target with sheer nonsense.",
    "topic_tags": ["AI", "Technology", "Russia", "Propaganda", "Disinformation"],
    "segments": [
        {
            "text": '<prosody rate="90%" pitch="-10%">In a shocking revelation that surprised absolutely no one, Russia has discovered that the secret to manipulating AI is... <emphasis level="strong">writing lots and lots of articles!</emphasis> <break time="0.5s"/> Who knew artificial intelligence could be fooled by the same technique used by college students padding their essays?</prosody>',
            "keywords": ["facepalm", "eye-roll", "sarcastic", "typing"],
        },
        {
            "text": '<prosody rate="110%">Meet Pravda, Russia\'s latest contribution to journalism, pumping out a modest <emphasis level="strong">THREE POINT SIX MILLION ARTICLES</emphasis> per year! <break time="0.5s"/> That\'s right folks, they\'re not trying to reach human readers - those are SO last century. They\'re targeting the hip new audience: chatbots!</prosody>',
            "keywords": ["robot", "information overload", "spam", "flooding"],
        },
        {
            "text": '<prosody pitch="+15%">And the best part? These articles get almost no human readers! <break time="0.5s"/> <prosody rate="85%">It\'s like having a conversation with yourself in an empty room, except the room is the entire internet, and you\'re hoping the AI algorithms are eavesdropping.</prosody></prosody>',
            "keywords": ["laughing", "empty room", "lonely", "talking to self"],
        },
    ],
}

script_json_2 = {
    "title": "Netflix's AI Upgrade Turns 80s Sitcom into Digital Horror Show",
    "description": "A satirical look at Netflix's disastrous attempt to use AI...",
    "topic_tags": ["AI", "Netflix", "Comedy"],
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

scripts = [
    ComedyScript.model_validate(script_json_1),
    ComedyScript.model_validate(script_json_2)
]

def convert_multiple_scripts_to_video(
    scripts: list[ComedyScript],  # List of ComedyScript objects
    elevenlabs_api_key: str,
    giphy_api_key: str,
    output_path: str = "output.mp4",
    frame_size=(1280, 720),
    codec="libx264",
    audio_codec="libmp3lame",
    fps=24,
    audio_bitrate="192k"
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
            frame_size=frame_size
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
            output_path,
            codec=codec,
            audio_codec=audio_codec,
            fps=fps,
            audio_bitrate=audio_bitrate
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
    scripts,
    eleven_labs_api_key,
    giphy_api_key,
    output_path="combined_output.mp4"
)