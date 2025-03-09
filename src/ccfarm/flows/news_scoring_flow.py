# src/orchestration_play/flows/news_scoring_flow.py
from uuid import UUID
from ccfarm.agents.digger.models import ArticleScore
from ccfarm.clients.news_client import NewsAPIClient
from ccfarm.persistence.scores_storage import ArticleScoresStore
from prefect import flow, task, get_run_logger
from prefect.blocks.system import Secret
from typing import Dict, List
from prefect.artifacts import create_markdown_artifact
from common.blocks import TeamsWebhook
from ccfarm.agents import Digger


@task(name="Initialize Digger with Dependencies")
def initialize_digger(news_api_secret_block: str, mongo_conn_secret_block: str, anthropic_api_secret_block: str
) -> Digger:
    """Initialize the Digger agent with all required dependencies"""
    api_key = Secret.load(anthropic_api_secret_block).get()
    news_client = NewsAPIClient(Secret.load(news_api_secret_block).get())
    articles_scores_store = ArticleScoresStore(Secret.load(mongo_conn_secret_block).get())
    
    return Digger(
        anthropic_api_key=api_key, 
        news_client=news_client, 
        scores_store=articles_scores_store
    )

@task(name="Process News Articles", retries=2, retry_delay_seconds=30)
def process_news_articles(
    digger: Digger, query: str, page_size: int, days_in_past: int
) -> List[Dict]:
    """Process news articles and return those meeting the threshold"""
    logger = get_run_logger()
    logger.info(f"Searching for articles with query: '{query}'")

    articles: list[dict] = digger.dig_for_news(
        query=query, page_size=page_size, days_in_past=days_in_past
    )

    return articles


@task(name="Create Results Artifact")
async def create_results_artifact(articles: List[Dict]) -> UUID:
    """Create a markdown artifact with the results"""
    logger = get_run_logger()

    if not articles:
        markdown = "# News Scoring Results\n\nNo articles met the scoring threshold."
        logger.info("No articles met the scoring threshold")
    else:
        markdown = (
            f"# News Scoring Results\n\nFound {len(articles)} high-potential comedy articles:\n\n"
        )

        for idx, article in enumerate(articles, 1):
            original = article.get("article", {})
            score_result: ArticleScore = article.get("score", {})
            
            markdown += f"## {idx}. {original.get('title')} - Score: {score_result.score}\n\n"
            markdown += f"**Reason:** {score_result.reason}\n\n"
            if description := original.get("description"):
                markdown += f"**Description:** {description}\n\n"

            if url := original.get("url"):
                markdown += f"**Source:** [{url}]({url})\n\n"

            markdown += "---\n\n"

    # Create the artifact
    artifact_id = await create_markdown_artifact(
        key="news-scoring-results",
        markdown=markdown,
        description="News Articles Scored for Comedy Potential",
    )

    return artifact_id


@task(name="Send Notification")
def send_notification(
    articles: List[Dict], query: str, webhook_name: str = "weather-teams-webhook"
):
    """Send notification with results via Teams webhook"""
    logger = get_run_logger()

    try:
        teams_block = TeamsWebhook.load(webhook_name)

        if not articles:
            message = f"📰 News scoring complete: No articles met the threshold for query '{query}'"
        else:
            message = f"📰 News scoring complete: Found {len(articles)} articles with comedy potential for query '{query}'\n\n"
            message += "\n".join(
                [
                    f"{idx}. {article['article']['title']} - Score: {article['score'].score}"
                    for idx, article in enumerate(articles, 1)
                ]
            )
        logger.info(f"Sending notification: {message}")
        teams_block.notify(message)
        logger.info("Notification sent successfully")
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        # Don't raise here to prevent flow failure just because of notification


@flow(name="Schema News Comedy Potential Flow")
def news_scoring_flow(
    query: str = "artificial intelligence",
    page_size: int = 20,
    days_in_past: int = 7,
    mongo_conn_secret_block: str = "dev-mongodb-conn-string",
    news_api_secret_block: str = "news-api-key",
    anthropic_api_secret_block: str = "anthropic-api-key",
    teams_webhook_name: str = "teams-webhook",
):
    """Flow to score news articles for comedy potential"""
    logger = get_run_logger()
    logger.info(f"Starting news scoring flow with query: {query}")    

    # Initialize Digger with all dependencies
    digger = initialize_digger(
        news_api_secret_block=news_api_secret_block,
        mongo_conn_secret_block=mongo_conn_secret_block,
        anthropic_api_secret_block=anthropic_api_secret_block
    )
    
    # Process articles
    scored_articles = process_news_articles(
        digger=digger, query=query, page_size=page_size, days_in_past=days_in_past
    )

    # Create artifact with results
    artifact_id = create_results_artifact(scored_articles)

    # Send notification
    send_notification(articles=scored_articles, query=query, webhook_name=teams_webhook_name)

    logger.info(f"News scoring flow completed with artifact ID: {artifact_id}")
    return scored_articles


if __name__ == "__main__":
    news_scoring_flow()
