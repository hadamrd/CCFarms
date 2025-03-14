from datetime import datetime
from typing import Any, Dict, List, Union
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from bson.objectid import ObjectId
import os

class ScriptStorage:
    """Storage handler for comedy scripts"""
    
    def __init__(self, connection_string, db_name="article_db", collection_name="comedy_scripts"):
        self.connection_string = connection_string
        if not self.connection_string:
            raise ValueError("MongoDB connection string required")
        
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
            
            # Create index on created_at for efficient sorting
            if "created_at_1" not in self.collection.index_information():
                self.collection.create_index("created_at")
                
            # Create index on source_articles for efficient querying
            if "source_articles_1" not in self.collection.index_information():
                self.collection.create_index("source_articles")
                
        except PyMongoError as e:
            print(f"Error initializing MongoDB: {e}")
            raise
    
    def store_script(
        self,
        title: str,
        script_data: Dict,
        source_articles: List[str]
    ) -> str:
        """Store a new comedy script with multiple source articles"""
        try:
            script_document = {
                "title": title,
                "script_data": script_data,
                "source_articles": source_articles,
                "created_at": datetime.now()
            }
            
            result = self.collection.insert_one(script_document)
            return str(result.inserted_id)
        except PyMongoError as e:
            print(f"Error storing script: {e}")
            raise
        
    def get_script(self, script_id: str) -> Any:
        """Retrieve a specific script by ID"""
        try:
            script = self.collection.find_one({"_id": ObjectId(script_id)})
            if script:
                script["_id"] = str(script["_id"])
            return script
            
        except Exception as e:
            print(f"Error retrieving script: {e}")
            return None
    
    def get_all_scripts(self, limit: int = 10) -> List[Dict]:
        """Get all scripts, sorted by creation date"""
        try:
            scripts = list(self.collection.find().sort("created_at", -1).limit(limit))
            
            # Convert ObjectId to string
            for script in scripts:
                script["_id"] = str(script["_id"])
                
            return scripts
            
        except PyMongoError as e:
            print(f"Error retrieving all scripts: {e}")
            return []
    
    def get_scripts_by_source(self, article_id: str) -> List[Dict]:
        """Get scripts that used a specific article as source"""
        try:
            scripts = list(self.collection.find({"source_article": article_id}))
            
            # Convert ObjectId to string
            for script in scripts:
                script["_id"] = str(script["_id"])
                
            return scripts
            
        except PyMongoError as e:
            print(f"Error retrieving scripts by source: {e}")
            return []
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
