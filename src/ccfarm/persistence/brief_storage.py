# src/orchestration_play/persistence/brief_storage.py
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from datetime import datetime
from typing import Optional, Dict, List
import os

class BriefStorage:
    def __init__(self, connection_string=None, db_name="article_db", collection_name="article_briefs"):
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
        try:
            self.client = MongoClient(self.connection_string)
            self.db = self.client[self.db_name]
            self.collection = self.db[self.collection_name]
            
            # Create unique index on article_id
            if "article_id_1" not in self.collection.index_information():
                self.collection.create_index("article_id", unique=True)
                
            # Create index on timestamp for efficient queries
            if "timestamp_1" not in self.collection.index_information():
                self.collection.create_index("timestamp")
                
        except PyMongoError as e:
            print(f"Error initializing MongoDB: {e}")
            raise
    
    def store_brief(self, article_id: str, model_output: Dict, metadata: Optional[Dict] = None):
        """Store any model output JSON with minimal required metadata"""
        document = {
            "article_id": article_id,
            "model_output": model_output,
            "timestamp": datetime.now()
        }
        
        # Add optional metadata if provided
        if metadata:
            document["metadata"] = metadata
            
        try:
            self.collection.update_one(
                {"article_id": article_id},
                {"$set": document},
                upsert=True
            )
        except PyMongoError as e:
            print(f"Error storing brief: {e}")
            raise
    
    def get_brief(self, article_id: str) -> Optional[Dict]:
        """Get a stored brief by article ID"""
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
        """Check if an article has been briefed"""
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
        """Get all stored briefs, most recent first"""
        try:
            results = self.collection.find().sort(
                "timestamp", -1
            ).limit(limit)
            
            return [{'doc': doc, "_id": str(doc["_id"])} for doc in results]
            
        except PyMongoError as e:
            print(f"Error retrieving briefs: {e}")
            return []
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
