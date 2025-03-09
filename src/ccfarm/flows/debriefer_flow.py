"""
Article analysis and brief generation orchestration flow.
"""

from typing import Dict, List, Optional, Set
from prefect import flow, get_run_logger, task
from prefect.blocks.system import Secret
from prefect.task_runners import SequentialTaskRunner

from ccfarm.agents import Debriefer
from ccfarm.clients.news_client import NewsAPIClient
from ccfarm.persistence.brief_storage import BriefStore
from ccfarm.persistence.scores_storage import ArticleScoresStore
from common.blocks.notifications.teams_webhook import TeamsWebhook


@task(name="Get Top Articles")
def get_top_articles(
    scores_storage: ArticleScoresStore,
    brief_storage: BriefStore,
    limit: int = 5,
    reanalyze_existing: bool = False,
) -> List[Dict]:
    """Retrieve top articles from cache, filtering already briefed ones unless reanalysis requested"""
    logger = get_run_logger()
    logger.info(f"Retrieving top articles (limit: {limit}, reanalyze: {reanalyze_existing})")

    # Get all cached articles
    scored_articles = scores_storage.list_scores()
    if not scored_articles:
        logger.warning("No scored articles found in storage")
        return []

    # Skip filtering if reanalysis is requested
    if reanalyze_existing:
        logger.info(f"Reanalyze flag set - returning top {limit} articles")
        return scored_articles[:limit]

    # Get already briefed article IDs for filtering
    try:
        existing_briefs = brief_storage.get_all_briefs(limit=1000)
        briefed_article_ids = {
            brief.get("article_id") for brief in existing_briefs if brief.get("article_id")
        }
        logger.info(
            f"Found {len(briefed_article_ids)} unique briefed article IDs to filter against"
        )
    except Exception as e:
        logger.error(f"Error retrieving existing briefs: {e}")
        briefed_article_ids = set()

    # Filter articles
    filtered_articles = [
        article for article in scored_articles if article.get("_id") not in briefed_article_ids
    ]

    logger.info(
        f"Filtered out {len(scored_articles) - len(filtered_articles)} already briefed articles"
    )
    return filtered_articles[:limit]


@task(name="Process Article", retries=2, retry_delay_seconds=60)
def process_article(
    debriefer: Debriefer, article: Dict, brief_storage: BriefStore
) -> Optional[Dict]:
    """Process a single article: fetch content, analyze, and store brief"""
    logger = get_run_logger()

    article_id = str(article.get("_id"))
    title = article.get("title", "Unknown title")
    url = article.get("url")

    # Check for valid URL
    if not url:
        logger.warning(f"Article {article_id} ({title}) has no URL - skipping")
        return None

    try:
        # Fetch content
        logger.info(f"Fetching and analyzing article: {title}")
        content = debriefer.news_client.fetch_article_content(url)

        if not content:
            logger.warning(f"Could not fetch content for {url}")
            return None

        # Analyze article
        article_with_content = article.copy()
        article_with_content["content"] = content
        model_output = debriefer.analyze_article(article_with_content)

        # Store brief
        brief_storage.store_brief(
            article_id=article_id,
            model_output=model_output.dict(),
            metadata={"title": title, "url": url},
        )

        return {"article_id": article_id, "title": title, "model_output": model_output}

    except Exception as e:
        logger.error(f"Error processing article {title}: {str(e)}")
        return None


@task(name="Process Articles")
def process_articles(
    anthropic_api_key: str, news_api_key: str, articles: List[Dict], brief_storage: BriefStore
) -> List[Dict]:
    """Process a batch of articles with the Debriefer agent"""
    logger = get_run_logger()
    logger.info(f"Starting analysis of {len(articles)} articles")

    if not articles:
        logger.info("No articles to analyze")
        return []

    # Initialize the Debriefer agent
    news_client = NewsAPIClient(news_api_key)
    debriefer = Debriefer(anthropic_api_key=anthropic_api_key, news_client=news_client)

    # Process each article
    processed_articles = []
    for article in articles:
        result = process_article(debriefer, article, brief_storage)
        if result:
            processed_articles.append(result)

    logger.info(f"Completed analysis of {len(processed_articles)} articles")
    return processed_articles


@task(name="Generate Results Summary")
def generate_results_summary(
    processed_articles: List[Dict], teams_webhook_block: Optional[str] = None
) -> str:
    """Generate summary and send notification if configured"""
    logger = get_run_logger()

    if not processed_articles:
        message = "No articles were analyzed in this run"
        logger.info(message)
        return message

    # Build results summary
    summary_lines = [f"Analyzed {len(processed_articles)} articles for comedy content:"]

    for idx, article in enumerate(processed_articles, 1):
        model_output = article.get("model_output", {})
        summary_lines.append(f"\n{idx}. {article.get('title')}")

        # Extract summary information
        if "summary" in model_output:
            summary_lines.append(f"   {model_output['summary']}")
        elif "core_story" in model_output and isinstance(model_output["core_story"], dict):
            if "simple_summary" in model_output["core_story"]:
                summary_lines.append(f"   {model_output['core_story']['simple_summary']}")

        # Add comedy potential if available
        if "comedy_potential" in model_output:
            summary_lines.append(f"   Comedy Potential: {model_output['comedy_potential']}/10")

    summary = "\n".join(summary_lines)
    logger.info(f"\nAnalysis Summary:\n{summary}")

    # Send notification if configured
    if teams_webhook_block:
        try:
            TeamsWebhook.load(teams_webhook_block).notify(f"Comedy Brief Analysis Results:\n\n{summary}")
        except Exception as e:
            logger.error(f"Failed to send Teams notification: {e}")

    return summary


@flow(name="Comedy Brief Analysis Flow", task_runner=SequentialTaskRunner())
def debriefer_flow(
    articles_limit: int = 5,
    reanalyze_existing: bool = False,
    mongodb_conn_secret_block: str = "dev-mongodb-conn-string",
    anthropic_api_secret_block: str = "anthropic-api-key",
    news_api_secret_block: str = "news-api-key",
    teams_webhook_block: Optional[str] = "teams-webhook",
) -> List[Dict]:
    """Orchestration flow to analyze top articles for comedy potential and store briefs"""
    logger = get_run_logger()
    logger.info(f"Starting debriefer flow with limit {articles_limit}")

    # Initialize storage clients
    conn_string = Secret.load(mongodb_conn_secret_block).get()
    brief_storage = BriefStore(conn_string)
    scores_storage = ArticleScoresStore(conn_string)

    # Get API keys from secrets
    anthropic_api_key = Secret.load(anthropic_api_secret_block).get()
    news_api_key = Secret.load(news_api_secret_block).get()

    # Get top articles for analysis
    top_articles = get_top_articles(
        scores_storage, brief_storage, articles_limit, reanalyze_existing
    )

    if not top_articles:
        logger.warning("No articles found to analyze")
        return []

    # Process articles
    processed_articles = process_articles(
        anthropic_api_key, news_api_key, top_articles, brief_storage
    )

    # Log results and send notification
    generate_results_summary(processed_articles, teams_webhook_block)

    logger.info(f"Debriefer flow completed successfully")
    return processed_articles


if __name__ == "__main__":
    debriefer_flow()
