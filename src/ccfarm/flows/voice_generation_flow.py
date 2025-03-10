"""
Voice generation flow for comedy scripts.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
import os

from prefect import flow, task, get_run_logger
from prefect.task_runners import SequentialTaskRunner
from prefect.blocks.system import Secret
from prefect.artifacts import create_markdown_artifact, create_link_artifact

from ccfarm.agents import VoiceGenerator
from ccfarm.persistence.script_storage import ScriptStorage


@task(name="Get Script Data")
def get_script_data(script_id: str, mongodb_conn_string: str) -> Optional[Dict]:
    """Retrieve the script data from storage by ID"""
    logger = get_run_logger()
    logger.info(f"Retrieving script with ID: {script_id}")
    
    try:
        script_storage = ScriptStorage(mongodb_conn_string)
        script = script_storage.get_script(script_id)
        
        if not script:
            logger.warning(f"Script with ID {script_id} not found")
            return None
            
        logger.info(f"Successfully retrieved script: {script.get('title', 'Untitled')}")
        return script
    except Exception as e:
        logger.error(f"Error retrieving script: {str(e)}")
        return None


@task(name="Generate Voice Audio", retries=2, retry_delay_seconds=60)
def generate_voice_audio(script: Dict, openai_api_key: str) -> Optional[str]:
    """Generate voice audio for the script"""
    logger = get_run_logger()
    
    if not script:
        logger.warning("No script data provided for voice generation")
        return None
    
    try:
        # Initialize VoiceGenerator agent
        voice_generator = VoiceGenerator(openai_api_key=openai_api_key)
        
        # Generate voice audio
        logger.info(f"Generating voice audio for script: {script.get('title', 'Untitled')}")
        audio_path = voice_generator.generate_voice_for_script(script)
        
        logger.info(f"Successfully generated voice audio: {audio_path}")
        return audio_path
        
    except Exception as e:
        logger.error(f"Error generating voice audio: {str(e)}")
        return None


@task(name="Update Script Storage")
def update_script_with_audio_path(
    script_id: str, 
    audio_path: str, 
    mongodb_conn_string: str
) -> bool:
    """Update the script record with the path to the generated audio file"""
    logger = get_run_logger()
    
    if not script_id or not audio_path:
        logger.warning("Missing script ID or audio path for storage update")
        return False
    
    try:
        script_storage = ScriptStorage(mongodb_conn_string)
        
        # Update script with audio path
        success = script_storage.update_script(
            script_id=script_id,
            update_data={"audio_path": audio_path, "voice_generated_at": datetime.now().isoformat()}
        )
        
        if success:
            logger.info(f"Successfully updated script {script_id} with audio path")
            return True
        else:
            logger.warning(f"Failed to update script {script_id} with audio path")
            return False
            
    except Exception as e:
        logger.error(f"Error updating script with audio path: {str(e)}")
        return False


@task(name="Create Artifacts")
def create_audio_artifacts(script: Dict, audio_path: Optional[str] = None) -> str:
    """Create Prefect artifacts for the generated audio"""
    logger = get_run_logger()
    
    if not script:
        logger.warning("No script data available to create artifact")
        return ""
    
    try:
        # Extract script components
        script_data = script.get("script_data", {})
        title = script_data.get("title", "Untitled Comedy Script")
        
        # Format as markdown
        markdown_content = f"# Voice Generation: {title}\n\n"
        
        if audio_path and os.path.exists(audio_path):
            # Add audio file information
            file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
            markdown_content += f"## Audio File\n\n"
            markdown_content += f"- **Path:** {audio_path}\n"
            markdown_content += f"- **Size:** {file_size_mb:.2f} MB\n"
            markdown_content += f"- **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            # Add segment information
            segments = script_data.get("segments", [])
            markdown_content += f"## Segments\n\n"
            markdown_content += f"Total segments: {len(segments)}\n\n"
            
            for i, segment in enumerate(segments):
                markdown_content += f"### Segment {i+1}\n\n"
                markdown_content += f"- **Text:** {segment.get('text', '')[:100]}...\n"
                markdown_content += f"- **Tone:** {segment.get('tone', 'neutral')}\n"
                markdown_content += f"- **Speed:** {segment.get('speed', 1.0)}\n"
                markdown_content += f"- **Pause After:** {segment.get('pause_after', 0.0)}s\n\n"
        else:
            markdown_content += "## No Audio Generated\n\n"
            markdown_content += "Voice generation was not successful or the audio file is missing.\n"
        
        # Create markdown artifact
        artifact_id = create_markdown_artifact(
            key=f"voice-generation-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            markdown=markdown_content,
            description=f"Voice Generation: {title}"
        )
        
        logger.info(f"Successfully created artifacts for voice generation")
        return artifact_id
        
    except Exception as e:
        logger.error(f"Error creating artifacts: {str(e)}")
        return ""


@flow(name="Voice Generation Flow", task_runner=SequentialTaskRunner())
def voice_generation_flow(
    script_id: str,
    mongodb_conn_secret_block: str = "dev-mongodb-conn-string",
    openai_api_secret_block: str = "openai-api-key",
) -> Optional[Dict[str, Any]]:
    """Generate voice audio from a comedy script"""
    logger = get_run_logger()
    logger.info(f"Starting voice generation flow for script ID: {script_id}")
    
    # Get connection string and API keys
    conn_string = Secret.load(mongodb_conn_secret_block).get()
    openai_api_key = Secret.load(openai_api_secret_block).get()
    
    # Get the script data
    script = get_script_data(script_id, conn_string)
    
    if not script:
        logger.warning(f"No script found with ID {script_id}")
        return None
    
    # Generate voice audio
    audio_path = generate_voice_audio(script, openai_api_key)
    
    if not audio_path:
        logger.warning("Voice generation failed")
        # Create artifacts anyway to document the failure
        artifact_id = create_audio_artifacts(script)
        return {
            "script_id": script_id,
            "success": False,
            "artifact_id": artifact_id
        }
    
    # Update script storage with audio path
    update_success = update_script_with_audio_path(script_id, audio_path, conn_string)
    
    # Create artifacts
    artifact_id = create_audio_artifacts(script, audio_path)
    
    # Return results
    logger.info("Voice generation flow completed successfully")
    return {
        "script_id": script_id,
        "audio_path": audio_path,
        "artifact_id": artifact_id,
        "success": update_success
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m ccfarm.flows.voice_generation_flow <script_id>")
        sys.exit(1)
    
    script_id = sys.argv[1]
    voice_generation_flow(script_id)