# src/orchestration_play/flows/debriefer_flow.py
from prefect import flow, task, get_run_logger
from prefect.task_runners import SequentialTaskRunner
from prefect.blocks.system import Secret
from typing import List, Dict
from datetime import datetime

from orchestration_play.blocks import NewsAPIBlock, ArticleCacheBlock, BriefStorageBlock
from orchestration_play.agents.debriefer import Debriefer
from orchestration_play.blocks.notifications.teams_webhook import TeamsWebhook

@task(name="Initialize Debriefer Agent")
def init_debriefer(api_key: str) -> Debriefer:
    """
    Initialize the Debriefer agent with the Anthropic API key.
    
    Args:
        api_key: Anthropic API key from Secret block
        
    Returns:
        Initialized Debriefer agent
    """
    return Debriefer(anthropic_api_key=api_key)

@task(name="Load Dependencies")
def load_dependencies(debriefer: Debriefer, news_api_block_name: str) -> Debriefer:
    """
    Load and inject the NewsAPI client into the Debriefer agent.
    
    Args:
        debriefer: Initialized Debriefer agent
        news_api_block_name: Name of the registered NewsAPIBlock
        
    Returns:
        Debriefer agent with dependencies injected
    """
    # Load NewsAPI client
    news_block = NewsAPIBlock.load(news_api_block_name)
    news_client = news_block.get_client()
    
    # Set news client in debriefer
    debriefer.news_client = news_client
    
    return debriefer

@task(name="Get Top Articles")
def get_top_articles(article_cache_block_name: str, brief_storage_block_name: str, limit: int = 5, reanalyze_existing: bool = False) -> List[Dict]:
    """
    Get the top N newest articles from the cache, filtering already briefed articles unless reanalyzing
    
    Args:
        article_cache_block_name: Name of the registered ArticleCacheBlock
        brief_storage_block_name: Name of the registered BriefStorageBlock
        limit: Number of articles to retrieve
        reanalyze_existing: Whether to include articles that have already been briefed
        
    Returns:
        List of articles from cache
    """
    logger = get_run_logger()
    logger.info(f"Retrieving top articles from cache (limit: {limit}, reanalyze: {reanalyze_existing})")
    
    # Initialize cache from block
    cache_block = ArticleCacheBlock.load(article_cache_block_name)
    article_cache = cache_block.get_article_cache()
    
    # Get all cached articles
    all_articles = article_cache.get_all_cached()
    
    # Sort by cached_at descending to get newest first
    sorted_articles = sorted(all_articles, key=lambda x: x.get('cached_at', datetime.min), reverse=True)
    
    # Filter out already briefed articles if not reanalyzing
    if not reanalyze_existing:
        logger.info("Filtering out already briefed articles")
        
        # Initialize brief storage from block
        brief_block = BriefStorageBlock.load(brief_storage_block_name)
        brief_storage = brief_block.get_brief_storage()
        
        # Filter articles
        filtered_articles = []
        for article in sorted_articles:
            article_id = article.get('_id')
            if not brief_storage.check_article_briefed(article_id):
                filtered_articles.append(article)
            else:
                logger.info(f"Skipping already briefed article: {article.get('title')}")
        
        # Use filtered list
        top_articles = filtered_articles[:limit]
        logger.info(f"Retrieved {len(top_articles)} new articles out of {len(sorted_articles)} total")
    else:
        # Use all articles
        top_articles = sorted_articles[:limit]
        logger.info(f"Retrieved {len(top_articles)} articles, including previously briefed ones")
    
    return top_articles

@task(name="Process and Analyze Articles")
def process_and_analyze_articles(debriefer: Debriefer, articles: List[Dict]) -> List[Dict]:
    """
    Process and analyze articles using the Debriefer's built-in method
    
    Args:
        debriefer: Debriefer agent with dependencies
        articles: List of article dictionaries from cache
        
    Returns:
        List of analyzed articles with briefs
    """
    logger = get_run_logger()
    logger.info(f"Starting detailed analysis of {len(articles)} articles")
    
    if not articles:
        logger.info("No articles to analyze")
        return []
    
    # Use Debriefer's built-in process_articles method
    processed_briefs = debriefer._process_articles(articles)
    
    # Convert to the format needed for storage
    analyzed_articles = []
    for idx, brief in enumerate(processed_briefs):
        original_article = articles[idx]
        analyzed_article = {
            'article_id': original_article.get('_id'),
            'title': original_article.get('title'),
            'url': original_article.get('url'),
            'original_score': original_article.get('score'),
            'original_reason': original_article.get('reason'),
            'brief': brief.dump_model(),  # Convert pydantic model to dict
            'analyzed_at': datetime.now()
        }
        
        analyzed_articles.append(analyzed_article)
        logger.info(f"Successfully analyzed: {original_article.get('title')}")
    
    logger.info(f"Completed analysis of {len(analyzed_articles)} articles")
    return analyzed_articles

@task(name="Store Briefs")
def store_briefs(brief_storage_block_name: str, analyzed_articles: List[Dict]) -> int:
    """
    Store analyzed articles in the brief storage
    
    Args:
        brief_storage_block_name: Name of the registered BriefStorageBlock
        analyzed_articles: List of articles with briefs
        
    Returns:
        Number of briefs stored
    """
    logger = get_run_logger()
    logger.info(f"Storing {len(analyzed_articles)} article briefs")
    
    if not analyzed_articles:
        logger.info("No briefs to store")
        return 0
    
    # Initialize brief storage from block
    brief_block = BriefStorageBlock.load(brief_storage_block_name)
    brief_storage = brief_block.get_brief_storage()
    
    # Store each brief
    count = 0
    for article in analyzed_articles:
        try:
            brief_storage.store_brief(
                article_id=article.get('article_id'),
                title=article.get('title'),
                url=article.get('url'),
                original_score=article.get('original_score'),
                original_reason=article.get('original_reason'),
                brief_data=article.get('brief'),
                analyzed_at=article.get('analyzed_at')
            )
            count += 1
        except Exception as e:
            logger.error(f"Error storing brief for {article.get('title')}: {e}")
    
    logger.info(f"Successfully stored {count} briefs")
    return count

@task(name="Log Results")
def log_results(analyzed_articles: List[Dict]) -> str:
    """
    Log the results of the article analysis process.
    
    Args:
        analyzed_articles: List of analyzed articles with briefs
    
    Returns:
        Summary text
    """
    logger = get_run_logger()
    
    if not analyzed_articles:
        message = "No articles were analyzed in this run"
        logger.info(message)
        return message
    
    logger.info(f"Analyzed {len(analyzed_articles)} articles for comedy content")
    
    # Build results summary
    summary_lines = []
    for idx, article in enumerate(analyzed_articles, 1):
        brief = article.get('brief', {})
        core_story = brief.get('core_story', {})
        summary_lines.append(f"{idx}. {article['title']}")
        if core_story and 'simple_summary' in core_story:
            summary_lines.append(f"   {core_story['simple_summary']}")
    
    summary = "\n".join(summary_lines)
    logger.info(f"\nAnalysis Summary:\n{summary}")
    return summary

@flow(name="Comedy Brief Analysis Flow", task_runner=SequentialTaskRunner())
def debriefer_flow(
    articles_limit: int = 5,
    reanalyze_existing: bool = False,
    news_api_block_name: str = "dev-newsapi-config",
    article_cache_block_name: str = "dev-article-cache",
    brief_storage_block_name: str = "dev-brief-storage",
):
    """
    Flow to analyze top comedy-potential articles with detailed brief.
    
    Args:
        articles_limit: Number of articles to process
        reanalyze_existing: Whether to reanalyze articles that have already been briefed
        news_api_block_name: Name of the registered NewsAPIBlock
        article_cache_block_name: Name of the registered ArticleCacheBlock
        brief_storage_block_name: Name of the registered BriefStorageBlock
    """
    logger = get_run_logger()
    logger.info(f"Starting debriefer flow with limit {articles_limit}, reanalyze_existing={reanalyze_existing}")
    
    # Get top articles from cache, filtering already briefed ones unless reanalysis requested
    top_articles = get_top_articles(
        article_cache_block_name=article_cache_block_name,
        brief_storage_block_name=brief_storage_block_name,
        limit=articles_limit,
        reanalyze_existing=reanalyze_existing
    )
    
    if not top_articles:
        logger.warning("No articles found to analyze")
        return []
    
    # Load Anthropic API key from Secret block
    secret_block = Secret.load("anthropic-api-key")
    api_key = secret_block.get()
    
    # Initialize Debriefer agent
    debriefer = init_debriefer(api_key)
    
    # Load and inject dependencies
    debriefer_with_deps = load_dependencies(debriefer, news_api_block_name)
    
    # Process and analyze articles with debriefer
    analyzed_articles = process_and_analyze_articles(debriefer_with_deps, top_articles)
    
    # Store results
    stored_count = store_briefs(brief_storage_block_name, analyzed_articles)
    
    # Log results and send notification
    summary = log_results(analyzed_articles)
    
    if analyzed_articles:
        try:
            teams_block = TeamsWebhook.load("weather-teams-webhook")
            teams_block.notify(f"Comedy Brief Analysis Results:\n\n{summary}")
        except Exception as e:
            logger.error(f"Failed to send Teams notification: {e}")
    
    logger.info(f"Debriefer flow completed. Analyzed {len(analyzed_articles)} articles, stored {stored_count} briefs")
    
    return analyzed_articles

if __name__ == "__main__":
    debriefer_flow()
