from orchestration_play.persistence.article_cache import ArticleCache
from prefect.blocks.core import Block
from typing import Optional

class ArticleCacheBlock(Block):
    """Block for managing ArticleCache connections."""
    
    _block_type_name = "Article Cache"
    _block_type_slug = "article-cache"
    _logo_url = "https://image.pngaaa.com/229/5858229-middle.png"
    
    connection_string: Optional[str] = None
    db_name: str = "article_db"
    collection_name: str = "article_scores"
    cache_days: int = 7
    
    def get_article_cache(self) -> ArticleCache:
        """
        Returns an initialized ArticleCache instance.
        
        Returns:
            ArticleCache: A configured ArticleCache instance
        """
        return ArticleCache(
            connection_string=self.connection_string,
            db_name=self.db_name,
            collection_name=self.collection_name,
            cache_days=self.cache_days
        )
