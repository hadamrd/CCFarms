import os
from typing import List, Optional
from prefect import flow, get_run_logger
from prefect.blocks.system import Secret
from ccfarm.agents.satirist.models import ComedyScript
from ccfarm.persistence.script_storage import ScriptStorage
from moviepy import concatenate_videoclips
from dotenv import load_dotenv  # For local testing fallback

# Function to fetch latest scripts (no @task, keeping it simple like your example)
def fetch_latest_scripts(
    script_storage: ScriptStorage,
    limit: int = 5
) -> List[ComedyScript]:
    logger = get_run_logger()
    logger.info(f"Fetching up to {limit} latest scripts from storage")

    try:
        # Get all scripts, sorted by insertion time (assuming MongoDB's _id timestamp)
        raw_scripts = script_storage.get_all_scripts(limit=limit)
        if not raw_scripts:
            logger.warning("No scripts found in storage")
            return []

        # Convert raw script dicts to ComedyScript objects
        scripts = []
        for script_data in raw_scripts:
            try:
                script = ComedyScript.model_validate(script_data.get("script_data", {}))
                scripts.append(script)
                logger.info(f"Loaded script: {script.title}")
            except Exception as e:
                logger.error(f"Error parsing script {script_data.get('title', 'unknown')}: {str(e)}")
        
        logger.info(f"Successfully fetched {len(scripts)} scripts")
        return scripts
    except Exception as e:
        logger.error(f"Error fetching scripts from storage: {str(e)}")
        return []

# Modified convert_multiple_scripts_to_video function
def convert_multiple_scripts_to_video(
    scripts: List[ComedyScript],
    elevenlabs_api_key: str,
    giphy_api_key: str,
    unsplash_api_key: str,
    output_path: str = "output.mp4",
    frame_size: tuple[int, int] = (1280, 720),
    codec: str = "libx264",
    audio_codec: str = "libmp3lame",
    fps: int = 24,
    audio_bitrate: str = "192k",
) -> Optional[str]:
    logger = get_run_logger()
    
    if not scripts:
        logger.info("No scripts provided to convert")
        return None

    logger.info(f"Processing {len(scripts)} comedy scripts")
    all_video_clips = []

    for i, script in enumerate(scripts):
        logger.info(f"Processing script {i+1}/{len(scripts)}: {script.title}")
        try:
            script_clip = script.convert_to_video(
                elevenlabs_api_key=elevenlabs_api_key,
                giphy_api_key=giphy_api_key,
                unsplash_api_key=unsplash_api_key,
                output_path=None,  # Don't export individual scripts
                frame_size=frame_size,
            )
            if script_clip:
                all_video_clips.append(script_clip)
                logger.info(f"Successfully processed script {i+1}")
            else:
                logger.warning(f"Failed to create video for script {i+1}: {script.title}")
        except Exception as e:
            logger.error(f"Error processing script {script.title}: {str(e)}")

    if not all_video_clips:
        logger.warning("No script videos were successfully created")
        return None

    try:
        logger.info(f"Concatenating {len(all_video_clips)} script videos")
        final_video = concatenate_videoclips(all_video_clips)
        logger.info(f"Writing final video to {output_path}")
        final_video.write_videofile(
            output_path,
            codec=codec,
            audio_codec=audio_codec,
            fps=fps,
            audio_bitrate=audio_bitrate
        )
        logger.info(f"Multiple scripts video created successfully: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Error creating combined video: {str(e)}")
        return None

# Prefect flow to orchestrate script fetching and video generation
@flow(name="Comedy Video Generation Flow")
def video_generation_flow(
    scripts_limit: int = 5,
    output_path: str = "combined_output.mp4",
    mongodb_conn_secret_block: str = "dev-mongodb-conn-string",
    elevenlabs_api_secret_block: str = "elevenlabs-api-key",
    giphy_api_secret_block: str = "giphy-api-key",
    unsplash_api_secret_block: str = "unsplash-api-key",
) -> Optional[str]:
    logger = get_run_logger()
    logger.info(f"Starting video generation flow with script limit {scripts_limit}")

    # Load secrets from Prefect Secret blocks
    conn_string = Secret.load(mongodb_conn_secret_block).get()
    elevenlabs_api_key = Secret.load(elevenlabs_api_secret_block).get()
    giphy_api_key = Secret.load(giphy_api_secret_block).get()
    unsplash_api_key = Secret.load(unsplash_api_secret_block).get()

    # Validate secrets
    if not all([conn_string, elevenlabs_api_key, giphy_api_key, unsplash_api_key]):
        logger.error("One or more required API keys or connection strings are missing")
        raise ValueError("Missing required secrets (MongoDB conn, ElevenLabs, Giphy, or Unsplash API key)")

    # Initialize storage
    script_storage = ScriptStorage(conn_string)

    # Step 1: Fetch latest scripts
    scripts = fetch_latest_scripts(script_storage, limit=scripts_limit)
    if not scripts:
        logger.warning("No scripts available to process into videos")
        return None

    # Step 2: Convert scripts to video
    video_path = convert_multiple_scripts_to_video(
        scripts=scripts,
        elevenlabs_api_key=elevenlabs_api_key,
        giphy_api_key=giphy_api_key,
        unsplash_api_key=unsplash_api_key,
        output_path=output_path,
    )

    if video_path:
        logger.info(f"Video generation flow completed successfully. Output: {video_path}")
    else:
        logger.warning("Video generation flow completed with no output")

    return video_path

if __name__ == "__main__":
    # For local testing with .env fallback
    load_dotenv()
    video_generation_flow(
        scripts_limit=5,
        output_path="combined_output.mp4",
        mongodb_conn_secret_block="dev-mongodb-conn-string",
        elevenlabs_api_secret_block="elevenlabs-api-key",
        giphy_api_secret_block="giphy-api-key",
        unsplash_api_secret_block="unsplash-api-key",
    )