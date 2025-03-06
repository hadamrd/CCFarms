# src/orchestration_play/persistence/brief_storage.py
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from datetime import datetime
from typing import Optional, Dict, List
import os

class BriefStorage:
    def __init__(self, connection_string=None, db_name="article_db", collection_name="article_briefs"):
        """
        Initialize brief storage with MongoDB backend
        
        Args:
            connection_string: MongoDB connection string
            db_name: MongoDB database name
            collection_name: MongoDB collection name
        """
        self.connection_string = connection_string or os.environ.get(
            "MONGODB_URL", 
            "mongodb://article_user:article_password@mongodb:27017/article_db?authSource=admin"
        )
        self.db_name = db_name
        self.collection_name = collection_name
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
            
            # Create unique index on article_id
            if "article_id_1" not in self.collection.index_information():
                self.collection.create_index("article_id", unique=True)
                
            # Create index on analyzed_at for efficient queries
            if "analyzed_at_1" not in self.collection.index_information():
                self.collection.create_index("analyzed_at")
                
        except PyMongoError as e:
            print(f"Error initializing MongoDB: {e}")
            raise
    
    def store_brief(self, article_id: str, title: str, url: str, 
                   original_score: int, original_reason: str, brief_data: Dict, analyzed_at: datetime):
        """
        Store a detailed article brief in the database
        
        Args:
            article_id: ID of the original article in cache
            title: Article title
            url: Article URL
            original_score: Original score from Digger
            original_reason: Original reason from Digger
            brief_data: Full brief data from Debriefer
            analyzed_at: Timestamp when analysis was completed
        """
        try:
            self.collection.update_one(
                {"article_id": article_id},
                {"$set": {
                    "article_id": article_id,
                    "title": title,
                    "url": url,
                    "original_score": original_score,
                    "original_reason": original_reason,
                    "brief": brief_data,
                    "analyzed_at": analyzed_at
                }},
                upsert=True
            )
            
        except PyMongoError as e:
            print(f"Error storing brief: {e}")
            raise
    
    def get_brief(self, article_id: str) -> Optional[Dict]:
        """
        Get a stored brief by article ID
        
        Args:
            article_id: ID of the article
            
        Returns:
            Brief dictionary or None if not found
        """
        try:
            result = self.collection.find_one({"article_id": article_id})
            
            if result:
                # Convert MongoDB _id to string for serialization
                result["_id"] = str(result["_id"])
                return result
                
            return None
            
        except PyMongoError as e:
            print(f"Error retrieving brief: {e}")
            return None

    def check_article_briefed(self, article_id: str) -> bool:
        """
        Check if an article has already been briefed
        
        Args:
            article_id: ID of the article to check
            
        Returns:
            True if the article has been briefed, False otherwise
        """
        try:
            result = self.collection.find_one(
                {"article_id": article_id},
                {"_id": 1}  # Only return _id field for efficiency
            )
            
            return result is not None
            
        except PyMongoError as e:
            print(f"Error checking article status: {e}")
            return False

    def get_all_briefs(self, limit: int = 100) -> List[Dict]:
        """
        Get all stored briefs, most recent first
        
        Args:
            limit: Maximum number of briefs to return
            
        Returns:
            List of brief dictionaries
        """
        try:
            results = self.collection.find().sort(
                "analyzed_at", -1  # Sort by analyzed_at descending
            ).limit(limit)
            
            # Convert MongoDB _id to string for serialization
            return [{**doc, "_id": str(doc["_id"])} for doc in results]
            
        except PyMongoError as e:
            print(f"Error retrieving briefs: {e}")
            return []
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
