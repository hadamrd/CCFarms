# src/orchestration_play/agents/digger.py
from prefect import get_run_logger
from autogen import AssistantAgent
import re
import json

class Digger(AssistantAgent):
    """
    AI agent that evaluates news articles for comedy potential on a scale of 1-10.
    Uses the Anthropic Claude API via autogen to analyze articles.
    """
    
    def __init__(self, anthropic_api_key: str, news_client=None, article_cache=None, model: str = "claude-3-5-sonnet-20241022"):
        """
        Initialize the Digger agent with required dependencies.
        
        Args:
            anthropic_api_key: API key for Anthropic
            news_client: Optional NewsAPI client (can be injected later)
            article_cache: Optional ArticleCache instance (can be injected later)
            model: Anthropic model to use
        """
        self.logger = get_run_logger()
        
        super().__init__(
            name="NewsScout",
            llm_config={
                "config_list": [{
                    "model": model,
                    "api_key": anthropic_api_key,
                    "api_base": "https://api.anthropic.com/v1/messages",
                    "api_type": "anthropic",
                }],
                "temperature": 0.3,  # More factual
                "timeout": 30,
            },
            system_message="""You are an AI Comedy Scout specializing in quick assessment of tech news comedy potential.
            
EXTREMELY SELECTIVE SCORING (1-10):
1-3: Regular tech news, no comedy value
4-6: Mildly interesting but not special
7-8: Strong comedy potential (needs multiple):
    - Clear tech industry ego/delusion
    - Obvious irony or hypocrisy
    - Rich personality-driven drama
9-10: Comedy gold (extremely rare, needs all):
    - Multiple layers of absurdity
    - Perfect setup for satire
    - Exceptional irony/controversy

BE HARSH IN SCORING. Most articles should score below 7.
Only truly exceptional stories deserve high scores.

Always return score in <brief_json> format."""
        )
        
        # These can be injected later if not provided during initialization
        self.news_client = news_client
        self.cache = article_cache
    
    def set_news_client(self, news_client):
        """Set the NewsAPI client after initialization"""
        self.news_client = news_client
    
    def set_article_cache(self, article_cache):
        """Set the ArticleCache after initialization"""
        self.cache = article_cache

    def quick_score_articles(self, articles: list[dict], threshold: int = 7) -> list[dict]:
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

    def _get_quick_score(self, article: dict) -> dict:
        """
        Get quick comedy potential score for a single article.
        
        Args:
            article: Article dictionary with title and description
            
        Returns:
            Dictionary with score and reason
        """
        prompt = f"""
        Rate comedy potential (1-10) for this tech news.
        BE EXTREMELY SELECTIVE. Score of 7+ should be rare.
        
        Title: {article['title']}
        Description: {article['description']}
        
        Return score and reason in <brief_json> format:
        <brief_json>
        {{
            "score": number (1-10),
            "reason": "one line explanation why this score"
        }}
        </brief_json>
        """
        
        try:
            self.logger.debug(f"Sending prompt to Anthropic for article: {article['title']}")
            response = self.generate_reply([{"content": prompt, "role": "user"}])
            result = self._extract_json(response.get("content", ""))
            return result
        except Exception as e:
            self.logger.error(f"Error scoring article: {e}")
            return {"score": 0, "reason": f"Error in scoring: {str(e)}"}

    def _extract_json(self, content: str) -> dict:
        """
        Extract JSON from between brief_json tags in the LLM response.
        
        Args:
            content: Response content from Anthropic
            
        Returns:
            Parsed JSON dictionary
        """
        pattern = r'<brief_json>(.*?)</brief_json>'
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            self.logger.error(f"No brief_json tags found in response: {content}")
            raise ValueError("No brief_json tags found")
        
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            self.logger.error(f"Invalid JSON in response: {match.group(1)}")
            raise ValueError(f"Invalid JSON in response: {match.group(1)}")

    def dig_for_news(self, query: str = "artificial intelligence", page_size: int = 20, threshold: int = 6) -> list[dict]:
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
