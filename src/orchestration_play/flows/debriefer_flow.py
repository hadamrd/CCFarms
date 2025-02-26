# src/orchestration_play/flows/debriefer_flow.py
from prefect import flow, task, get_run_logger
from prefect.task_runners import SequentialTaskRunner
from prefect.blocks.system import Secret
from typing import List, Dict, Optional, Any
from datetime import datetime

from orchestration_play.blocks import NewsAPIBlock, ArticleCacheBlock, BriefStorageBlock, TeamsWebhook
from orchestration_play.agents import Debriefer


def safe_model_dump(model: Any) -> Dict:
    if hasattr(model, "model_dump"):
        # Pydantic v2
        return model.model_dump()
    elif hasattr(model, "dict"):
        # Pydantic v1
        return model.dict()
    else:
        # Fallback approach
        return {k: getattr(model, k) for k in model.__annotations__}


@task(name="Initialize Debriefer Agent")
def init_debriefer(api_key: str) -> Debriefer:
    return Debriefer(anthropic_api_key=api_key)


@task(name="Load Dependencies")
def load_dependencies(debriefer: Debriefer, news_api_block_name: str) -> Debriefer:
    # Load NewsAPI client
    news_block = NewsAPIBlock.load(news_api_block_name)
    news_client = news_block.get_client()
    
    # Set news client in debriefer
    debriefer.news_client = news_client
    
    return debriefer


@task(name="Get Top Articles")
def get_top_articles(article_cache_block_name: str, brief_storage_block_name: str, limit: int = 5, reanalyze_existing: bool = False) -> List[Dict]:
    logger = get_run_logger()
    logger.info(f"Retrieving top articles from cache (limit: {limit}, reanalyze: {reanalyze_existing})")
    
    # Initialize cache from block
    cache_block = ArticleCacheBlock.load(article_cache_block_name)
    article_cache = cache_block.get_article_cache()
    
    # Initialize brief storage from block
    brief_block = BriefStorageBlock.load(brief_storage_block_name)
    brief_storage = brief_block.get_brief_storage()
    
    # Get all cached articles
    all_articles = article_cache.get_all_cached()
    
    # Sort by cached_at descending to get newest first
    sorted_articles = sorted(all_articles, key=lambda x: x.get('cached_at', datetime.min), reverse=True)
    
    # Pre-load all briefed article IDs for efficient filtering
    briefed_article_ids = set()
    if not reanalyze_existing:
        try:
            # Get all existing briefs
            existing_briefs = brief_storage.get_all_briefs(limit=1000)
            logger.info(f"Found {len(existing_briefs)} existing briefs in storage")
            
            # Extract article IDs into a set for O(1) lookups
            briefed_article_ids = {brief.get('article_id') for brief in existing_briefs if brief.get('article_id')}
            
            logger.info(f"Loaded {len(briefed_article_ids)} unique briefed article IDs to filter against")
        except Exception as e:
            logger.error(f"Error retrieving existing briefs: {e}")
    
    # Filter articles
    if not reanalyze_existing:
        filtered_articles = []
        filtered_count = 0
        
        for article in sorted_articles:
            article_id = article.get('_id')
            
            if article_id not in briefed_article_ids:
                filtered_articles.append(article)
            else:
                filtered_count += 1
                logger.info(f"Skipping already briefed article: {article.get('title')}")
        
        logger.info(f"Filtered out {filtered_count} already briefed articles")
        top_articles = filtered_articles[:limit]
    else:
        top_articles = sorted_articles[:limit]
    
    logger.info(f"Selected {len(top_articles)} articles for analysis")
    return top_articles

@task(name="Initialize Brief Storage")
def init_brief_storage(brief_storage_block_name: str):
    brief_block = BriefStorageBlock.load(brief_storage_block_name)
    return brief_block.get_brief_storage()


@task(name="Analyze and Store Article", retries=2, retry_delay_seconds=60)
def analyze_and_store_article(debriefer: Debriefer, article: Dict, brief_storage) -> Optional[Dict]:
    logger = get_run_logger()
    
    try:
        logger.info(f"Analyzing article: {article.get('title')}")
        
        # First make sure we have the URL to fetch content
        url = article.get('url')
        if not url:
            logger.warning(f"Skipping article with no URL: {article.get('title')}")
            return None
        
        # Fetch article content
        try:
            # Try both method names for compatibility
            if hasattr(debriefer.news_client, "fetch_article_content"):
                content = debriefer.news_client.fetch_article_content(url)
            elif hasattr(debriefer.news_client, "_fetch_article_content"):
                content = debriefer.news_client.fetch_article_content(url)
            else:
                logger.error("News client has no fetch_article_content method")
                return None
        except Exception as e:
            logger.error(f"Error fetching content: {str(e)}")
            return None
            
        if not content:
            logger.warning(f"Could not fetch content for: {url}")
            return None
            
        # Add content to article for analysis
        article_with_content = article.copy()
        article_with_content['content'] = content
        
        # Analyze the article
        brief = debriefer.analyze_article(article_with_content)
        
        # Create analyzed article with brief
        analyzed_article = {
            'article_id': article.get('_id'),
            'title': article.get('title'),
            'url': article.get('url'),
            'original_score': article.get('score'),
            'original_reason': article.get('reason'),
            'brief': safe_model_dump(brief),
            'analyzed_at': datetime.now()
        }
        
        # Store brief immediately after successful analysis
        brief_storage.store_brief(
            article_id=analyzed_article['article_id'],
            title=analyzed_article['title'],
            url=analyzed_article['url'],
            original_score=analyzed_article['original_score'],
            original_reason=analyzed_article['original_reason'],
            brief_data=analyzed_article['brief'],
            analyzed_at=analyzed_article['analyzed_at']
        )
        
        # Add this to analyze_and_store_article function after storing the brief
        # Verify the brief was stored
        verification = brief_storage.check_article_briefed(analyzed_article['article_id'])
        if verification:
            logger.info(f"Verified brief was successfully stored for: {article.get('title')}")
        else:
            logger.warning(f"Could not verify brief storage for: {article.get('title')}")
    
        logger.info(f"Successfully analyzed and stored brief for: {article.get('title')}")
        return analyzed_article
        
    except Exception as e:
        logger.error(f"Error analyzing article {article.get('title')}: {str(e)}")
        return None


@task(name="Analyze Multiple Articles")
def analyze_articles(debriefer: Debriefer, articles: List[Dict], brief_storage) -> List[Dict]:
    logger = get_run_logger()
    logger.info(f"Starting detailed analysis of {len(articles)} articles")
    
    if not articles:
        logger.info("No articles to analyze")
        return []
    
    # Process each article individually
    analyzed_articles = []
    for article in articles:
        result = analyze_and_store_article(debriefer, article, brief_storage)
        if result:
            analyzed_articles.append(result)
    
    logger.info(f"Completed analysis of {len(analyzed_articles)} articles")
    return analyzed_articles


@task(name="Log Results")
def log_results(analyzed_articles: List[Dict]) -> str:
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
    
    # Initialize brief storage
    brief_storage = init_brief_storage(brief_storage_block_name)
    
    # Process and analyze articles with debriefer, storing each one as it's processed
    analyzed_articles = analyze_articles(debriefer_with_deps, top_articles, brief_storage)
    
    # Log results and send notification
    summary = log_results(analyzed_articles)
    
    if analyzed_articles:
        try:
            teams_block = TeamsWebhook.load("weather-teams-webhook")
            teams_block.notify(f"Comedy Brief Analysis Results:\n\n{summary}")
        except Exception as e:
            logger.error(f"Failed to send Teams notification: {e}")
    
    logger.info(f"Debriefer flow completed. Successfully analyzed and stored {len(analyzed_articles)} briefs")
    
    return analyzed_articles


if __name__ == "__main__":
    debriefer_flow()
