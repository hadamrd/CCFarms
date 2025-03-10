"""
Comedy script generation orchestration flow.
"""
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from prefect import flow, task, get_run_logger
from prefect.task_runners import SequentialTaskRunner
from prefect.blocks.system import Secret
from prefect.artifacts import create_markdown_artifact, create_link_artifact

from ccfarm.agents import Satirist
from ccfarm.persistence.brief_storage import BriefStore
from ccfarm.persistence.script_storage import ScriptStorage
from ccfarm.flows.debriefer_flow import debriefer_flow
from common.blocks.notifications.teams_webhook import TeamsWebhook


@task(name="Get Recent Briefs")
def get_recent_briefs(brief_storage: BriefStore, limit: int = 5) -> List[Dict]:
    """Retrieve the most recent article briefs from storage"""
    logger = get_run_logger()
    logger.info(f"Retrieving {limit} most recent article briefs")
    
    # Get briefs directly from storage
    briefs = brief_storage.get_all_briefs(limit=limit)
    if not briefs:
        logger.warning("No briefs found in storage")
        return []
    
    # Extract model output from each brief
    processed_briefs = []
    for brief in briefs:
        if 'doc' in brief and 'model_output' in brief['doc']:
            processed_briefs.append(brief['doc']['model_output'])
    
    # Sort by analyzed_at (newest first)
    sorted_briefs = sorted(
        processed_briefs,
        key=lambda x: x.get('analyzed_at', datetime.min),
        reverse=True
    )
    
    logger.info(f"Retrieved {len(sorted_briefs)} briefs for comedy script generation")
    return sorted_briefs


@task(name="Generate Comedy Script", retries=2, retry_delay_seconds=60)
def generate_comedy_script(anthropic_api_key: str, briefs: List[Dict]) -> Optional[Dict]:
    """Generate a comedy script from the analyzed article briefs"""
    logger = get_run_logger()
    
    if not briefs:
        logger.warning("No briefs available for comedy script generation")
        return None
    
    try:
        # Initialize Satirist agent
        satirist = Satirist(anthropic_api_key=anthropic_api_key)
        
        # Generate script
        logger.info(f"Generating comedy script based on {len(briefs)} briefs")
        script = satirist.generate_comedy_script(briefs)
        logger.info("Successfully generated comedy script")
        return script
        
    except Exception as e:
        logger.error(f"Error generating comedy script: {str(e)}")
        return None


@task(name="Store Comedy Script")
def store_comedy_script(script: Dict, script_storage: ScriptStorage) -> Tuple[bool, Optional[str]]:
    """Store the generated comedy script in the database"""
    logger = get_run_logger()
    
    if not script:
        logger.warning("No script to store")
        return False, None
    
    try:
        # Extract script data
        script_data = script["script_data"]
        
        # Store script
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


@task(name="Create Artifacts")
def create_artifacts(script: Dict, script_id: Optional[str] = None) -> str:
    """Create Prefect artifacts for the generated script in structured format"""
    logger = get_run_logger()
    
    if not script or not script.get("script_data"):
        logger.warning("No script data available to create artifact")
        return ""
    
    try:
        # Extract script components with new structure
        script_data = script["script_data"]
        title = script_data.get("title", "Untitled Comedy Script")
        description = script_data.get("description", "")
        segments = script_data.get("segments", [])
        
        # Format as markdown
        markdown_content = f"# {title}\n\n"
        markdown_content += f"_{description}_\n\n"
        markdown_content += f"_Generated on {script.get('generated_at')} from {script.get('article_count', 0)} news articles_\n\n"
        
        # Format segments in a readable way
        markdown_content += "## Voice Segments\n\n"
        
        for i, segment in enumerate(segments):
            markdown_content += f"### Segment {i+1}\n\n"
            markdown_content += f"**Text:** {segment.get('text', '')}\n\n"
            markdown_content += f"**Tone:** {segment.get('tone', 'neutral')}\n\n"
            markdown_content += f"**Speed:** {segment.get('speed', 1.0)}\n\n"
            markdown_content += f"**Pause After:** {segment.get('pause_after', 0.0)}s\n\n"
        
        # Add source information
        if script.get("source_articles"):
            source_count = len(script.get("source_articles", []))
            markdown_content += f"\n\n## Sources\n\nBased on {source_count} news articles\n\n"
        
        # Create markdown artifact
        artifact_id = create_markdown_artifact(
            key=f"comedy-script-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            markdown=markdown_content,
            description=f"Comedy Script: {title}"
        )
        
        logger.info(f"Successfully created artifacts for script: {title}")
        return artifact_id
        
    except Exception as e:
        logger.error(f"Error creating artifacts: {str(e)}")
        return ""


@task(name="Send Notification")
def send_notification(script: Dict, success: bool, webhook_block_name: Optional[str] = None) -> None:
    """Send a notification with script details to Teams channel"""
    logger = get_run_logger()
    
    if not success or not script or not webhook_block_name:
        return
    
    try:
        # Extract script details
        script_data = script["script_data"]
        title = script_data.get("title", "Untitled Comedy Script")
        description = script_data.get("description", "")
        
        # Create preview (truncate body text for notification)
        body_preview = script_data.get("body", "")
        if len(body_preview) > 500:
            body_preview = body_preview[:500] + "...\n\n*(truncated)*"
        
        # Build notification message
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
        logger.info(f"Sent notification for script: {title}")
        
    except Exception as e:
        logger.error(f"Error sending notification: {str(e)}")


@flow(name="Comedy Script Generation Flow", task_runner=SequentialTaskRunner())
def comedy_script_flow(
    brief_limit: int = 12,
    run_debriefer: bool = False,
    mongodb_conn_secret_block: str = "dev-mongodb-conn-string",
    anthropic_api_secret_block: str = "anthropic-api-key",
    teams_webhook_block: Optional[str] = "teams-webhook",
) -> Optional[Dict[str, Any]]:
    """Generate comedy scripts from news article briefs"""
    logger = get_run_logger()
    logger.info(f"Starting comedy script flow with brief_limit={brief_limit}")
    
    # Get connection string and API key
    conn_string = Secret.load(mongodb_conn_secret_block).get()
    anthropic_api_key = Secret.load(anthropic_api_secret_block).get()
    
    # Initialize storage clients directly
    brief_storage = BriefStore(conn_string)
    script_storage = ScriptStorage(conn_string)
    
    # Optionally run debriefer flow first
    if run_debriefer:
        logger.info("Running debriefer flow to analyze new articles")
        debriefer_results = debriefer_flow(
            mongodb_conn_secret_block=mongodb_conn_secret_block,
            anthropic_api_secret_block=anthropic_api_secret_block
        )
        analyzed_count = len(debriefer_results) if debriefer_results else 0
        logger.info(f"Debriefer flow completed with {analyzed_count} analyzed articles")
    
    # Get recent briefs
    briefs = get_recent_briefs(brief_storage, brief_limit)
    
    if not briefs:
        logger.warning("No briefs available for comedy script generation")
        return None
    
    # Generate comedy script
    script = generate_comedy_script(anthropic_api_key, briefs)
    
    if not script:
        logger.warning("Failed to generate comedy script")
        return None
    
    # Store the script
    success, script_id = store_comedy_script(script, script_storage)
    
    # Create artifacts
    artifact_id = create_artifacts(script, script_id)
    
    # Send notification
    send_notification(script, success, teams_webhook_block)
    
    # Return results
    logger.info("Comedy script flow completed successfully")
    return {
        "script": script,
        "script_id": script_id,
        "artifact_id": artifact_id,
        "success": success
    }


if __name__ == "__main__":
    comedy_script_flow()