# src/orchestration_play/flows/news_scoring_flow.py
from uuid import UUID
from common.blocks import TeamsWebhook
from prefect import flow, task, get_run_logger
from prefect.blocks.system import Secret
from typing import Dict, List
from prefect.artifacts import create_markdown_artifact

from ccfarm.blocks import NewsAPIBlock, ArticleCacheBlock
from ccfarm.agents import Digger


@task(name="Initialize Digger with Dependencies")
def initialize_digger(
    api_key: str, news_api_block_name: str, article_cache_block_name: str
) -> Digger:
    """Initialize the Digger agent with all required dependencies"""
    logger = get_run_logger()

    # Load and set NewsAPI client
    logger.info(f"Loading NewsAPI from block: {news_api_block_name}")
    news_client = NewsAPIBlock.load(news_api_block_name).get_client()

    # Load and set ArticleCache
    logger.info(f"Loading ArticleCache from block: {article_cache_block_name}")
    scores_cache = ArticleCacheBlock.load(article_cache_block_name).get_article_cache()

    # Initialize Digger with API key
    digger = Digger(anthropic_api_key=api_key, news_client=news_client, scores_cache=scores_cache)

    return digger

@task(name="Process News Articles", retries=2, retry_delay_seconds=30)
def process_news_articles(digger: Digger, query: str, page_size: int, threshold: int) -> List[Dict]:
    """Process news articles and return those meeting the threshold"""
    logger = get_run_logger()
    logger.info(f"Searching for articles with query: '{query}', threshold: {threshold}")

    try:
        articles: list[dict] = digger.dig_for_news(
            query=query, page_size=page_size, threshold=threshold
        )
    except Exception as e:
        logger.error(f"Error processing news articles: {e}")
        raise
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
            markdown += f"## {idx}. {article['title']} - Score: {article['score']}\n\n"
            markdown += f"**Reason:** {article['reason']}\n\n"

            original = article.get("original_article", {})
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
                    f"{idx}. {article['title']} - Score: {article['score']}"
                    for idx, article in enumerate(articles, 1)
                ]
            )

        teams_block.notify(message)
        logger.info("Notification sent successfully")
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        # Don't raise here to prevent flow failure just because of notification


@flow(name="Schema News Comedy Potential Flow")
def news_scoring_flow(
    query: str = "artificial intelligence",
    page_size: int = 20,
    threshold: int = 6,
    news_api_block_name: str = "dev-newsapi-config",
    article_cache_block_name: str = "dev-article-cache",
    teams_webhook_name: str = "weather-teams-webhook",
):
    """Flow to score news articles for comedy potential"""
    logger = get_run_logger()
    logger.info(f"Starting news scoring flow with query: {query}")

    # Load Anthropic API key from Secret block
    api_key = Secret.load("anthropic-api-key").get()

    # Initialize Digger with all dependencies
    digger = initialize_digger(
        api_key=api_key,
        news_api_block_name=news_api_block_name,
        article_cache_block_name=article_cache_block_name,
    )

    # Process articles
    scored_articles = process_news_articles(
        digger=digger, query=query, page_size=page_size, threshold=threshold
    )

    # Create artifact with results
    artifact_id = create_results_artifact(scored_articles)

    # Send notification
    send_notification(articles=scored_articles, query=query, webhook_name=teams_webhook_name)

    logger.info(f"News scoring flow completed with artifact ID: {artifact_id}")
    return scored_articles


if __name__ == "__main__":
    news_scoring_flow()
