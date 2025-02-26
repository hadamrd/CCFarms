from datetime import datetime
from typing import List, Dict, Optional, Any, Union
from prefect.blocks.core import Block
from pydantic import Field
from pymongo import MongoClient
from bson.objectid import ObjectId


class ScriptStorage:
    """Storage handler for comedy scripts"""
    
    def __init__(self, connection_string: str, database: str, collection: str):
        """
        Initialize script storage with MongoDB connection details
        
        Args:
            connection_string: MongoDB connection string
            database: Database name
            collection: Collection name for scripts
        """
        self.client = MongoClient(connection_string)
        self.db = self.client[database]
        self.collection = self.db[collection]
    
    def store_script(
        self,
        title: str,
        script_data: Dict,
        source_articles: List[str],
        generated_at: Union[datetime, str],
        article_count: int
    ) -> str:
        """
        Store a new comedy script in the database
        
        Args:
            title: Title of the comedy script
            script_data: The full script data (JSON structure)
            source_articles: List of article IDs used as sources
            generated_at: Timestamp when the script was generated
            article_count: Number of articles used to generate the script
            
        Returns:
            ID of the stored script
        """
        # Ensure datetime is in ISO format string if it's a datetime object
        if isinstance(generated_at, datetime):
            generated_at = generated_at.isoformat()
            
        script_document = {
            "title": title,
            "script_data": script_data,
            "source_articles": source_articles,
            "generated_at": generated_at,
            "article_count": article_count,
            "created_at": datetime.now()
        }
        
        result = self.collection.insert_one(script_document)
        return str(result.inserted_id)
    
    def get_script(self, script_id: str) -> Optional[Dict]:
        """
        Retrieve a comedy script by ID
        
        Args:
            script_id: ID of the script to retrieve
            
        Returns:
            Script document if found, None otherwise
        """
        try:
            script = self.collection.find_one({"_id": ObjectId(script_id)})
            if script:
                script["_id"] = str(script["_id"])
            return script
        except Exception:
            return None
    
    def get_all_scripts(self, limit: int = 10) -> List[Dict]:
        """
        Retrieve the most recent comedy scripts
        
        Args:
            limit: Maximum number of scripts to retrieve
            
        Returns:
            List of script documents
        """
        scripts = list(self.collection.find().sort("created_at", -1).limit(limit))
        
        # Convert ObjectId to string
        for script in scripts:
            script["_id"] = str(script["_id"])
            
        return scripts
    
    def get_scripts_by_source(self, article_id: str) -> List[Dict]:
        """
        Retrieve all scripts that used a specific article as source
        
        Args:
            article_id: ID of the source article
            
        Returns:
            List of script documents
        """
        scripts = list(self.collection.find({"source_articles": article_id}))
        
        # Convert ObjectId to string
        for script in scripts:
            script["_id"] = str(script["_id"])
            
        return scripts
