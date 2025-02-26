# article_cache.py
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import os

class ArticleCache:
    def __init__(self, connection_string=None, db_name="article_db", collection_name="article_scores", cache_days=7):
        """
        Initialize article cache with MongoDB backend
        
        Args:
            connection_string: MongoDB connection string
            db_name: MongoDB database name
            collection_name: MongoDB collection name
            cache_days: Number of days to keep articles in cache
        """
        self.connection_string = connection_string or os.environ.get(
            "MONGODB_URL", 
            "mongodb://article_user:article_password@mongodb:27017/article_db?authSource=admin"
        )
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
    
    def get_cached_score(self, url: str) -> Optional[Dict]:
        """
        Get cached score for article if it exists and is not expired
        
        Returns:
            Dict with score info or None if not found/expired
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=self.cache_days)
            
            result = self.collection.find_one({
                "url": url,
                "cached_at": {"$gt": cutoff_date}
            })
            
            if result:
                # Convert MongoDB _id to string for serialization
                result["_id"] = str(result["_id"])
                return result
                
            return None
            
        except PyMongoError as e:
            print(f"Error retrieving cached score: {e}")
            return None
    
    def cache_score(self, url: str, title: str, score: int, reason: str):
        """Cache a new article score"""
        try:
            current_time = datetime.now()
            
            self.collection.update_one(
                {"url": url},
                {"$set": {
                    "url": url,
                    "title": title,
                    "score": score,
                    "reason": reason,
                    "cached_at": current_time
                }},
                upsert=True
            )
            
        except PyMongoError as e:
            print(f"Error caching score: {e}")
            raise
    
    def get_all_cached(self) -> List[Dict]:
        """Get all non-expired cached articles"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.cache_days)
            
            results = self.collection.find(
                {"cached_at": {"$gt": cutoff_date}}
            ).sort("score", -1)  # Sort by score descending
            
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
