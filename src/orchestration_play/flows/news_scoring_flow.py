# src/orchestration_play/flows/news_scoring_flow.py
from orchestration_play.blocks.notifications.teams_webhook import TeamsWebhook
from prefect import flow, task
from prefect.blocks.system import Secret
from typing import Dict, List

from orchestration_play.blocks import NewsAPIBlock, ArticleCacheBlock
from orchestration_play.agents.digger import Digger


@task(name="Initialize Digger Agent")
def init_digger(api_key: str) -> Digger:
    """
    Initialize the Digger agent with the Anthropic API key.
    
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


@task(name="Log Results")
def log_results(articles: List[Dict]) -> str:
    """
    Log the results of the news scoring process.
    
    Args:
        articles: List of scored articles
    """
    from prefect import get_run_logger
    logger = get_run_logger()
    
    logger.info(f"Found {len(articles)} high-potential comedy articles")
    # build results summary brief
    summary = "\n".join([f"{idx}. {article['title']} - Score: {article['score']}" for idx, article in enumerate(articles, 1)])
    logger.info(f"\nSummary: {summary}")
    return summary


@flow(name="News Comedy Potential Flow")
def news_scoring_flow(
    query: str = "artificial intelligence", 
    page_size: int = 20,
    threshold: int = 6,
    news_api_block_name: str = "dev-newsapi-config",
    article_cache_block_name: str = "dev-article-cache",
):
    """
    Flow to fetch, score, and analyze news articles for comedy potential.
    
    Args:
        query: Search query for news articles
        page_size: Number of articles to fetch
        threshold: Minimum score threshold (1-10)
        news_api_block_name: Name of the registered NewsAPIBlock
        article_cache_block_name: Name of the registered ArticleCacheBlock
        
    Returns:
        List of scored articles above threshold
    """
    # Load Anthropic API key from Secret block
    secret_block = Secret.load("anthropic-api-key")
    api_key = secret_block.get()
    
    # Initialize Digger agent
    digger = init_digger(api_key)
    
    # Load and inject dependencies
    digger_with_deps = load_dependencies(digger, news_api_block_name, article_cache_block_name)
    
    # Process articles
    scored_articles = process_news_articles(digger_with_deps, query, page_size, threshold)
    
    # Log results
    summary = log_results(scored_articles)
    teams_block = TeamsWebhook.load("weather-teams-webhook")
    teams_block.notify(summary)
    
    return scored_articles
