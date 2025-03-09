# src/orchestration_play/persistence/article_cache.py
from ccfarm.agents.digger.models import ArticleScore
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from datetime import datetime, timedelta
from typing import Dict, List
import os

class ArticleScoresStore:
    def __init__(self, connection_string, db_name="article_db", collection_name="article_scores", cache_days=7):
        self.connection_string = connection_string or os.environ.get("MONGODB_URL")
        if not self.connection_string:
            raise ValueError("MongoDB connection string required")
        
        self.db_name = db_name
        self.collection_name = collection_name
        self.cache_days = cache_days
        self.client = None
        self.db = None
        self.collection = None
        self._init_db()
        
    def _init_db(self):
        """Initialize database connection and create indexes"""
        try:
            self.client = MongoClient(self.connection_string)
            self.db = self.client[self.db_name]
            self.collection = self.db[self.collection_name]
            
            # Create unique index on URL
            if "url_1" not in self.collection.index_information():
                self.collection.create_index("url", unique=True)
                
            # Create index on cached_at for efficient cleanup
            if "cached_at_1" not in self.collection.index_information():
                self.collection.create_index("cached_at")
                
        except PyMongoError as e:
            print(f"Error initializing MongoDB: {e}")
            raise
    
    def get_score(self, url: str) -> ArticleScore|None:
        try:
            cutoff_date = datetime.now() - timedelta(days=self.cache_days)
            
            result = self.collection.find_one({
                "url": url,
                "cached_at": {"$gt": cutoff_date}
            })
            
            if not result:
                return None
            
            return ArticleScore.parse_obj(result['score_result'])
            
        except PyMongoError as e:
            print(f"Error retrieving cached score: {e}")
            return None
    
    def save_score(self, url: str, title: str, score_result: ArticleScore):
        """Cache a new article score"""
        try:
            current_time = datetime.now()
            
            doc = {
                "url": url,
                "title": title,
                "cached_at": current_time,
                "score_result": score_result.dict(),
            }
            
            self.collection.update_one(
                {"url": url},
                {"$set": doc},
                upsert=True
            )
            
        except PyMongoError as e:
            print(f"Error caching score: {e}")
            raise
    
    def list_scores(self, sort_field: str = "score_result.score", limit: int = 50) -> List[Dict]:
        """Get all non-expired cached articles"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.cache_days)
            
            query = {"cached_at": {"$gt": cutoff_date}}
            
            results = self.collection.find(query).sort(sort_field, -1).limit(limit)
            
            # Convert MongoDB _id to string for serialization
            return [{**doc, "_id": str(doc["_id"])} for doc in results]
            
        except PyMongoError as e:
            print(f"Error retrieving cached articles: {e}")
            return []
    
    def cleanup_expired(self):
        """Remove expired cache entries"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.cache_days)
            
            result = self.collection.delete_many(
                {"cached_at": {"$lt": cutoff_date}}
            )
            
            return result.deleted_count
            
        except PyMongoError as e:
            print(f"Error cleaning up expired entries: {e}")
            return 0
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
