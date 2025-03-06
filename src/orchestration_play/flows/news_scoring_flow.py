# src/orchestration_play/flows/news_scoring_flow.py
from prefect import flow, task, get_run_logger
from prefect.blocks.system import Secret
from typing import Dict, List
from prefect.artifacts import create_markdown_artifact

from orchestration_play.blocks import NewsAPIBlock, ArticleCacheBlock, TeamsWebhook
from orchestration_play.agents import Digger


@task(name="Initialize Schema Digger Agent")
def init_schema_digger(api_key: str) -> Digger:
    """
    Initialize the Schema-based Digger agent with the Anthropic API key.
    
    Args:
        api_key: Anthropic API key from Secret block
        
    Returns:
        Initialized Digger agent
    """
    return Digger(anthropic_api_key=api_key)


@task(name="Load Dependencies")
def load_dependencies(digger: Digger, news_api_block_name: str, article_cache_block_name: str) -> Digger:
    """
    Load and inject the NewsAPI client and ArticleCache into the Digger agent.
    
    Args:
        digger: Initialized Digger agent
        news_api_block_name: Name of the registered NewsAPIBlock
        article_cache_block_name: Name of the registered ArticleCacheBlock
        
    Returns:
        Digger agent with dependencies injected
    """
    # Load NewsAPI client
    news_block = NewsAPIBlock.load(news_api_block_name)
    news_client = news_block.get_client()
    digger.set_news_client(news_client)
    
    # Load ArticleCache
    cache_block = ArticleCacheBlock.load(article_cache_block_name)
    article_cache = cache_block.get_article_cache()
    digger.set_article_cache(article_cache)
    
    return digger


@task(name="Process News Articles")
def process_news_articles(digger: Digger, query: str, page_size: int, threshold: int) -> List[Dict]:
    """
    Process news articles using the Digger agent.
    
    Args:
        digger: Digger agent with dependencies
        query: Search query for news
        page_size: Number of articles to fetch
        threshold: Minimum score threshold
        
    Returns:
        List of scored articles above threshold
    """
    return digger.dig_for_news(query=query, page_size=page_size, threshold=threshold)


@task(name="Create Results Artifact")
def create_results_artifact(articles: List[Dict]) -> str:
    """
    Create a markdown artifact with the results.
    
    Args:
        articles: List of scored articles
        
    Returns:
        Artifact ID
    """
    logger = get_run_logger()
    
    if not articles:
        markdown = "# News Scoring Results\n\nNo articles met the scoring threshold."
        logger.info("No articles met the scoring threshold")
    else:
        markdown = f"# News Scoring Results\n\nFound {len(articles)} high-potential comedy articles:\n\n"
        
        for idx, article in enumerate(articles, 1):
            markdown += f"## {idx}. {article['title']} - Score: {article['score']}\n\n"
            markdown += f"**Reason:** {article['reason']}\n\n"
            # Include description if available
            if article.get('original_article', {}).get('description'):
                markdown += f"**Description:** {article['original_article']['description']}\n\n"
            # Include URL if available
            if article.get('original_article', {}).get('url'):
                markdown += f"**Source:** [{article['original_article']['url']}]({article['original_article']['url']})\n\n"
            markdown += "---\n\n"
    
    # Create the artifact
    artifact_id = create_markdown_artifact(
        key=f"news-scoring-results",
        markdown=markdown,
        description="News Articles Scored for Comedy Potential"
    )
    
    return artifact_id


@flow(name="Schema News Comedy Potential Flow")
def news_scoring_flow(
    query: str = "artificial intelligence", 
    page_size: int = 20,
    threshold: int = 6,
    news_api_block_name: str = "dev-newsapi-config",
    article_cache_block_name: str = "dev-article-cache",
):
    """
    Flow to fetch, score, and analyze news articles for comedy potential using the schema-based agent.
    
    Args:
        query: Search query for news articles
        page_size: Number of articles to fetch
        threshold: Minimum score threshold (1-10)
        news_api_block_name: Name of the registered NewsAPIBlock
        article_cache_block_name: Name of the registered ArticleCacheBlock
        
    Returns:
        List of scored articles above threshold
    """
    logger = get_run_logger()
    logger.info(f"Starting schema-based news scoring flow with query: {query}")
    
    # Load Anthropic API key from Secret block
    secret_block = Secret.load("anthropic-api-key")
    api_key = secret_block.get()
    
    # Initialize Digger agent
    digger = init_schema_digger(api_key)
    
    # Load and inject dependencies
    digger_with_deps = load_dependencies(digger, news_api_block_name, article_cache_block_name)
    
    # Process articles
    scored_articles = process_news_articles(digger_with_deps, query, page_size, threshold)
    
    # Create artifact with results
    artifact_id = create_results_artifact(scored_articles)
    
    # Send notification via Teams
    try:
        teams_block = TeamsWebhook.load("weather-teams-webhook")
        
        if not scored_articles:
            teams_block.notify(f"📰 News scoring complete: No articles met the threshold for query '{query}'")
        else:
            message = f"📰 News scoring complete: Found {len(scored_articles)} articles with comedy potential for query '{query}'\n\n"
            message += "\n".join([f"{idx}. {article['title']} - Score: {article['score']}" for idx, article in enumerate(scored_articles, 1)])
            teams_block.notify(message)
    except Exception as e:
        logger.error(f"Failed to send Teams notification: {e}")
    
    logger.info(f"Schema news scoring flow completed with artifact ID: {artifact_id}")
    return scored_articles


if __name__ == "__main__":
    news_scoring_flow()