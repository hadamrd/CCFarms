# src/orchestration_play/agents/digger.py
import os
import json
from typing import List, Dict, Optional
from prefect import get_run_logger

from orchestration_play.agents.schema_agent import SchemaAgent

class Digger(SchemaAgent):
    """
    AI agent that evaluates news articles for comedy potential on a scale of 1-10.
    Uses the SchemaAgent base class for structured prompting and response validation.
    """
    
    def __init__(
        self, 
        anthropic_api_key: str, 
        news_client=None, 
        article_cache=None, 
        model: str = "claude-3-5-sonnet-20241022",
        schema_file: Optional[str] = None
    ):
        """
        Initialize the Digger agent with required dependencies.
        
        Args:
            anthropic_api_key: API key for Anthropic
            news_client: Optional NewsAPI client (can be injected later)
            article_cache: Optional ArticleCache instance (can be injected later)
            model: Anthropic model to use
            schema_file: Path to JSON schema file (optional)
        """
        # Set up the directory for this agent
        self.agent_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Load schema from file or use default
        schema_path = schema_file or os.path.join(
            self.agent_dir, 
            "digger_schema.json"
        )
        
        # Load schema from file or use a simple default schema
        if os.path.exists(schema_path):
            with open(schema_path, 'r') as f:
                response_schema = json.load(f)
        else:
            raise ValueError("Schema file not found: " + schema_path)
        
        # Initialize base agent with JSON schema
        super().__init__(
            name="NewsScout",
            response_schema=response_schema,
            anthropic_api_key=anthropic_api_key,
            model=model,
            template_dir=self.agent_dir,
            response_tag="brief_json",
            temperature=0.3  # More factual
        )
        
        self.logger = get_run_logger()
        self.news_client = news_client
        self.cache = article_cache
    
    def set_news_client(self, news_client):
        """Set the NewsAPI client after initialization"""
        self.news_client = news_client
    
    def set_article_cache(self, article_cache):
        """Set the ArticleCache after initialization"""
        self.cache = article_cache

    def quick_score_articles(self, articles: List[Dict], threshold: int = 7) -> List[Dict]:
        """
        Quickly score articles based on title/description, returning those above threshold.
        
        Args:
            articles: list of article dictionaries from NewsAPI
            threshold: Minimum score (1-10) to include in results
            
        Returns:
            list of scored articles above threshold, sorted by score descending
        """
        if not self.cache:
            self.logger.error("ArticleCache not set - call set_article_cache() first")
            raise ValueError("ArticleCache not initialized")
            
        scored_articles = []
        
        for article in articles:
            if isinstance(article, str):
                self.logger.error(f"Invalid article format: {article}")
                raise ValueError("Article must be a dictionary, got string instead: " + article)
                
            if not article.get('title') or not article.get('description'):
                self.logger.warning("Skipping article with missing title or description")
                continue
                
            url = article.get('url')
            if not url:
                self.logger.warning("Skipping article with missing URL")
                continue

            # Check cache first
            self.logger.info(f"Checking cache for article: {article['title']}")
            cached = self.cache.get_cached_score(url)
            
            if cached:
                self.logger.info(f"Found cached article: {cached['title']} with score {cached['score']}")
                if cached['score'] >= threshold:
                    scored_articles.append({
                        'title': cached['title'],
                        'score': cached['score'],
                        'reason': cached['reason'],
                        'original_article': article
                    })
                continue

            # Score new articles
            self.logger.info(f"Scoring new article: {article['title']}")
            score = self._get_quick_score(article)
            
            self.logger.info(f"Article scored: {article['title']} - Score: {score['score']}")
            self.cache.cache_score(
                url=url,
                title=article['title'],
                score=score['score'],
                reason=score['reason']
            )

            if score['score'] >= threshold:
                scored_articles.append({
                    'title': article['title'],
                    'score': score['score'],
                    'reason': score['reason'],
                    'original_article': article
                })

        return sorted(scored_articles, key=lambda x: x['score'], reverse=True)

    def _get_quick_score(self, article: Dict) -> Dict:
        """
        Get quick comedy potential score for a single article using SchemaAgent.
        
        Args:
            article: Article dictionary with title and description
            
        Returns:
            Dictionary with score and reason
        """
        try:
            self.logger.debug(f"Scoring article: {article['title']}")
            
            # Use the base agent's process method with the score_prompt.j2 template
            return self.process(
                prompt_template="score_prompt.j2",
                article=article
            )
            
        except Exception as e:
            self.logger.error(f"Error scoring article: {article.get('title', 'Unknown')}: {e}")
            return {"score": 0, "reason": f"Error in scoring: {str(e)}"}

    def dig_for_news(self, query: str = "artificial intelligence", page_size: int = 20, threshold: int = 6) -> List[Dict]:
        """
        Main method to fetch and score news articles.
        
        Args:
            query: Search query for news articles
            page_size: Number of articles to fetch
            threshold: Minimum score threshold (1-10)
            
        Returns:
            list of scored articles above threshold
        """
        if not self.news_client:
            self.logger.error("NewsAPI client not set - call set_news_client() first")
            raise ValueError("NewsAPI client not initialized")
            
        if not self.cache:
            self.logger.error("ArticleCache not set - call set_article_cache() first")
            raise ValueError("ArticleCache not initialized")
        
        # Get articles from news client
        self.logger.info(f"Fetching articles for query: {query}, page_size: {page_size}")
        response = self.news_client.get_everything(
            query=query,
            page_size=page_size
        )
        
        articles = response.get('articles', [])
        if not articles:
            self.logger.error("No articles found for query")
            raise Exception("No articles found!")

        # Get quick scores and shortlist
        self.logger.info(f"Scoring {len(articles)} articles with threshold {threshold}")
        shortlisted = self.quick_score_articles(articles, threshold=threshold)
        self.logger.info(f"Found {len(shortlisted)} articles above threshold")

        # Clean up expired cache entries
        self.logger.info("Cleaning up expired cache entries")
        cleanup_count = self.cache.cleanup_expired()
        self.logger.info(f"Removed {cleanup_count} expired entries from cache")
        
        return shortlisted