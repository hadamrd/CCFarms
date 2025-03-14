import os
from typing import List, Dict, cast
from ccfarm.agents.base_agent import BaseAgent
from ccfarm.agents.scout.models import ArticleScore
from ccfarm.clients.news_client import NewsAPIClient
from prefect import get_run_logger
from datetime import datetime, timedelta


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ccfarm.persistence.scores_storage import ArticleScoresStore


class ArticleScorer(BaseAgent):
    """
    AI agent that evaluates news articles for comedy potential on a scale of 1-20.
    Uses the BaseAgent class for structured prompting and response validation.
    """

    news_client: NewsAPIClient

    def __init__(
        self, anthropic_api_key: str, news_client: NewsAPIClient, scores_store: "ArticleScoresStore"
    ):
        # Set up the directory for this agent
        self.agent_dir = os.path.dirname(os.path.abspath(__file__))

        # Configure LLM settings for AutoGen
        llm_config = {
            "config_list": [
                {
                    "model": "claude-3-7-sonnet-20250219",
                    "api_key": anthropic_api_key,
                    "api_base": "https://api.anthropic.com/v1/messages",
                    "api_type": "anthropic",
                }
            ],
            "temperature": 0.3,  # More factual assessments
        }

        # Initialize base agent
        super().__init__(
            name="NewsScout",
            llm_config=llm_config,
            template_dir=self.agent_dir,
        )

        self.logger = get_run_logger()
        self.news_client = news_client
        self.cache = scores_store

    def set_news_client(self, news_client):
        """Set the NewsAPI client after initialization"""
        self.news_client = news_client

    def set_article_cache(self, article_cache):
        """Set the ArticleCache after initialization"""
        self.cache = article_cache

    def quick_score_articles(self, articles: List[Dict]) -> list[tuple[dict, ArticleScore]]:
        """
        Quickly score articles based on title/description, returning those above threshold.
        """
        if not self.cache:
            self.logger.error("ArticleCache not set - call set_article_cache() first")
            raise ValueError("ArticleCache not initialized")

        scored_articles = []

        for article in articles:
            if not article.get("title") or not article.get("description"):
                self.logger.warning("Skipping article with missing title or description")
                continue

            url = article.get("url")
            if not url:
                self.logger.warning("Skipping article with missing URL")
                continue

            # Check cache first
            self.logger.info(f"Checking cache for article: {article['title']}")
            article_score = self.cache.get_score(url)

            if article_score:
                self.logger.info(f"Found cached score of value {article_score.model_dump()}")
                scored_articles.append((article, article_score))
                continue

            # Score new articles
            self.logger.info(f"Scoring new article: {article['title']}")
            article_score = self._get_quick_score(article)

            self.logger.info(f"Article scored: {article['title']} - Score: {article_score.score}")
            self.cache.save_score(url=url, title=article["title"], score_result=article_score)

            scored_articles.append((article, article_score))

        return sorted(scored_articles, key=lambda x: x[1].score, reverse=True)

    def _get_quick_score(self, article: Dict) -> ArticleScore:
        """
        Get quick comedy potential score for a single article.
        """
        try:
            self.logger.debug(f"Scoring article: {article['title']}")

            score = cast(
                ArticleScore,
                self.generate_reply(
                    prompt_template="score_prompt.j2",
                    response_tag="brief_json",
                    response_model=ArticleScore,
                    article=article,
                ),
            )
            return score
        except Exception as e:
            self.logger.error(f"Error scoring article: {article.get('title', 'Unknown')}: {e}")
            return ArticleScore(score=0, reason=f"Error in scoring: {str(e)}")

    def dig_for_news(
        self,
        query: str = "artificial intelligence",
        page_size: int = 20,
        days_in_past: int = 7,
        sort_by: str = "relevancy",
        language: str = "en",
    ) -> List[Dict]:
        """
        Main method to fetch and score news articles.
        Returns only the sorted list of articles with their scores.

        Args:
            query: Search term for articles
            page_size: Number of articles to fetch
            days_in_past: How many days to look back for articles

        Returns:
            List of articles sorted by comedy potential score (highest first)
        """
        if not self.news_client:
            self.logger.error("NewsAPI client not set - call set_news_client() first")
            raise ValueError("NewsAPI client not initialized")

        if not self.cache:
            self.logger.error("ArticleCache not set - call set_article_cache() first")
            raise ValueError("ArticleCache not initialized")

        # Get articles from news client
        self.logger.info(f"Fetching articles for query: {query}, page_size: {page_size}")

        # Get articles from news client with time constraint
        last_week = (datetime.now() - timedelta(days=days_in_past)).strftime("%Y-%m-%d")

        response = self.news_client.get_everything(
            query=query,
            page_size=page_size,
            from_date=last_week,
            sort_by=sort_by,
            language=language,
        )

        articles = response.get("articles", [])
        if not articles:
            raise RuntimeError("No articles found!")

        # Get quick scores for articles
        self.logger.info(f"Scoring {len(articles)} articles")
        scored_articles = self.quick_score_articles(articles)

        # Clean up expired cache entries
        self.logger.info("Cleaning up expired cache entries")
        cleanup_count = self.cache.cleanup_expired()
        self.logger.info(f"Removed {cleanup_count} expired entries from cache")

        # Return only the sorted list of articles with embedded scores
        return [
            {**article, "comedy_score": article_score.score, "score_reason": article_score.reason}
            for article, article_score in scored_articles
        ]
