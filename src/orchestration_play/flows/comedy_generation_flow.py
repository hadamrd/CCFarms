from orchestration_play.persistence.brief_storage import BriefStorage
from orchestration_play.persistence.script_storage import ScriptStorage
from prefect import flow, task, get_run_logger
from prefect.task_runners import SequentialTaskRunner
from prefect.blocks.system import Secret
from typing import List, Dict, Optional
from datetime import datetime

from orchestration_play.blocks import BriefStorageBlock, TeamsWebhook, ScriptStorageBlock
from orchestration_play.agents import Satirist
from orchestration_play.flows.debriefer_flow import debriefer_flow
from prefect.artifacts import create_markdown_artifact, create_link_artifact


@task(name="Initialize Satirist Agent")
def init_satirist(api_key: str) -> Satirist:
    """Initialize the Satirist agent with the Anthropic API key"""
    return Satirist(anthropic_api_key=api_key)


@task(name="Get Recent Briefs")
def get_recent_briefs(brief_storage_block_name: str, limit: int = 5) -> List[Dict]:
    """Retrieve the most recent article briefs from storage"""
    logger = get_run_logger()
    logger.info(f"Retrieving {limit} most recent article briefs")
    
    # Initialize brief storage from block
    brief_block = BriefStorageBlock.load(brief_storage_block_name)
    brief_storage: BriefStorage = brief_block.get_brief_storage()
    
    # Get most recent briefs
    recent_briefs = brief_storage.get_all_briefs(limit=limit)
    recent_briefs = [ b['doc']['model_output'] for b in recent_briefs ]
    # Sort by analyzed_at descending to get newest first
    sorted_briefs = sorted(
        recent_briefs, 
        key=lambda x: x.get('analyzed_at', datetime.min), 
        reverse=True
    )
    
    logger.info(f"Retrieved {len(sorted_briefs)} briefs for comedy script generation")
    return sorted_briefs


@task(name="Initialize Script Storage")
def init_script_storage(script_storage_block_name: str):
    """Initialize the storage for comedy scripts"""
    script_block = ScriptStorageBlock.load(script_storage_block_name)
    return script_block.get_script_storage()


@task(name="Generate Comedy Script", retries=2, retry_delay_seconds=60)
def generate_comedy_script(satirist: Satirist, briefs: List[Dict]) -> Optional[Dict]:
    """Generate a comedy script from the analyzed article briefs"""
    logger = get_run_logger()
    
    if not briefs:
        logger.warning("No briefs available for comedy script generation")
        return None
    
    try:
        logger.info(f"Generating comedy script based on {len(briefs)} briefs")
        script = satirist.generate_comedy_script(briefs)
        logger.info("Successfully generated comedy script")
        return script
    except Exception as e:
        logger.error(f"Error generating comedy script: {str(e)}")
        return None


@task(name="Store Comedy Script")
def store_comedy_script(script: Dict, script_storage: ScriptStorage) -> tuple[bool, str|None]:
    """Store the generated comedy script in the database"""
    logger = get_run_logger()
    
    if not script:
        logger.warning("No script to store")
        return False, None
    
    try:
        # Extract data from the new script_data format
        script_data = script["script_data"]
        
        script_id = script_storage.store_script(
            title=script_data.get("title", "Untitled Comedy Script"),
            script_data=script_data,
            source_articles=script["source_articles"],
            generated_at=script["generated_at"],
            article_count=script["article_count"]
        )
        logger.info(f"Successfully stored comedy script with ID: {script_id}")
        return True, script_id
    except Exception as e:
        logger.error(f"Error storing comedy script: {str(e)}")
        return False, None


@task(name="Send Script Notification")
def send_notification(script: Dict, success: bool, webhook_block_name: str) -> None:
    """Send a notification with script highlights to the teams channel"""
    logger = get_run_logger()
    
    if not success or not script:
        logger.warning("No successful script generation to notify about")
        return
    
    try:
        # Create a preview of the script for the notification
        script_data = script["script_data"]
        title = script_data.get("title", "Untitled Comedy Script")
        description = script_data.get("description", "")
        body = script_data.get("body", "")
        
        # Extract a preview of the body content
        body_preview = body[:150] + "..." if len(body) > 150 else body
        
        # Create notification message
        message = f"""🎭 **New Comedy Script Generated: {title}**

*Description:*
{description}

*Preview:*
{body_preview}

*Generated from {script['article_count']} news articles*
"""
        
        # Send notification
        teams_block = TeamsWebhook.load(webhook_block_name)
        teams_block.notify(message)
        logger.info("Successfully sent script notification")
    except Exception as e:
        logger.error(f"Error sending notification: {str(e)}")


@task(name="Create Script Artifact")
def create_script_artifact(script: Dict, script_id: Optional[str] = None) -> str:
    """
    Create a Prefect artifact for the generated comedy script.
    
    Args:
        script: The generated comedy script dictionary
        script_id: The database ID of the stored script (if available)
        
    Returns:
        The artifact ID
    """
    logger = get_run_logger()
    
    if not script or not script.get("script_data"):
        logger.warning("No script data available to create artifact")
        return ""
    
    try:
        script_data = script["script_data"]
        title = script_data.get("title", "Untitled Comedy Script")
        description = script_data.get("description", "")
        body = script_data.get("body", "")
        
        # Format the script content as markdown
        markdown_content = f"# {title}\n\n"
        markdown_content += f"_{description}_\n\n"
        markdown_content += f"_Generated on {script.get('generated_at', datetime.now().isoformat())} from {script.get('article_count', 0)} news articles_\n\n"
        
        # Add the full markdown body as-is
        markdown_content += body
        
        # Add source information
        if script.get("source_articles"):
            markdown_content += "\n\n## Sources\n\n"
            markdown_content += f"Based on {len(script.get('source_articles', []))} news articles\n\n"
        
        # Create the artifact
        artifact_id = create_markdown_artifact(
            key=f"comedy-script-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            markdown=markdown_content,
            description=f"Comedy Script: {title}"
        )
        
        # Create link artifact if script_id is available
        if script_id:
            link_artifact_id = create_link_artifact(
                key=f"comedy-script-db-{script_id}",
                link=f"mongodb://comedy_scripts/{script_id}",
                description=f"Database link for comedy script: {title}"
            )
            logger.info(f"Created link artifact with ID: {link_artifact_id}")
        
        logger.info(f"Successfully created script artifact with ID: {artifact_id}")
        return artifact_id
    except Exception as e:
        logger.error(f"Error creating script artifact: {str(e)}")
        return ""


@flow(name="Comedy Script Generation Flow", task_runner=SequentialTaskRunner())
def comedy_script_flow(
    brief_limit: int = 5,
    run_debriefer: bool = True,
    brief_storage_block_name: str = "dev-brief-storage",
    script_storage_block_name: str = "dev-script-storage",
    webhook_block_name: str = "weather-teams-webhook",
):
    """
    End-to-end flow that optionally runs the debriefer flow first,
    then generates a comedy script based on the most recent article briefs.
    
    Args:
        brief_limit: Maximum number of briefs to use for script generation
        run_debriefer: Whether to run the debriefer flow first to analyze new articles
        brief_storage_block_name: Name of the brief storage block
        script_storage_block_name: Name of the script storage block
        webhook_block_name: Name of the Teams webhook block for notifications
    
    Returns:
        Generated comedy script if successful, None otherwise
    """
    logger = get_run_logger()
    logger.info(f"Starting comedy script flow with brief_limit={brief_limit}, run_debriefer={run_debriefer}")
    
    # Optionally run the debriefer flow first to analyze new articles
    if run_debriefer:
        logger.info("Running debriefer flow to analyze new articles")
        debriefer_results = debriefer_flow()
        logger.info(f"Debriefer flow completed with {len(debriefer_results) if debriefer_results else 0} analyzed articles")
    
    # Get the most recent briefs for script generation
    recent_briefs = get_recent_briefs(
        brief_storage_block_name=brief_storage_block_name,
        limit=brief_limit
    )
    
    if not recent_briefs:
        logger.warning("No briefs available for comedy script generation")
        return None
    
    # Load Anthropic API key from Secret block
    secret_block = Secret.load("anthropic-api-key")
    api_key = secret_block.get()
    
    # Initialize Satirist agent
    satirist = init_satirist(api_key)
    
    # Initialize script storage
    script_storage = init_script_storage(script_storage_block_name)
    
    # Generate comedy script
    script = generate_comedy_script(satirist, recent_briefs)
    
    if not script:
        logger.warning("Failed to generate comedy script")
        return None
    
    # Store the script
    store_success, script_id = store_comedy_script(script, script_storage)
    
    # Create Prefect artifact for the script
    artifact_id = create_script_artifact(script, script_id)
    
    # Send notification
    send_notification(script, store_success, webhook_block_name)
    
    logger.info(f"Comedy script flow completed successfully with artifact ID: {artifact_id}")
    return {
        "script": script,
        "script_id": script_id,
        "artifact_id": artifact_id
    }


if __name__ == "__main__":
    comedy_script_flow()