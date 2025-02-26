#!/usr/bin/env python3
"""
MongoDB storage module for network metrics.
Simple and focused module for storing and retrieving network metrics.
"""

from datetime import datetime
from typing import List, Dict
from pymongo import MongoClient

class MetricsStorage:
    """
    Storage handler for network telemetry metrics.
    Provides methods to store and retrieve metrics data from MongoDB.
    """
    
    def __init__(
        self, 
        connection_string: str, 
        database: str, 
        metrics_collection: str = "metrics",
        anomalies_collection: str = "anomalies"
    ):
        """
        Initialize metrics storage with MongoDB connection details.
        
        Args:
            connection_string: MongoDB connection string
            database: Database name
            metrics_collection: Collection name for metrics
            anomalies_collection: Collection name for anomalies
        """
        self.client = MongoClient(connection_string)
        self.db = self.client[database]
        self.metrics_collection = self.db[metrics_collection]
        self.anomalies_collection = self.db[anomalies_collection]
        
        # Create basic indexes
        self._create_indexes()
    
    def _create_indexes(self):
        """Creates indexes for better query performance."""
        # Create index on timestamp and device_id for metrics
        self.metrics_collection.create_index([("timestamp", -1)])
        self.metrics_collection.create_index([("device_id", 1)])
    
    def store_metrics(self, metrics_data: List[Dict]) -> bool:
        """
        Store network metrics in the database.
        
        Args:
            metrics_data: List of metrics data dictionaries
            
        Returns:
            bool: True if storage was successful, False otherwise
        """
        try:
            if not metrics_data:
                return True  # Nothing to store
                
            # Add storage timestamp
            for metric in metrics_data:
                metric["stored_at"] = datetime.now()
            
            # Insert metrics into collection
            result = self.metrics_collection.insert_many(metrics_data)
            
            return len(result.inserted_ids) == len(metrics_data)
        except Exception as e:
            print(f"Error storing metrics: {str(e)}")
            return False
    
    def store_anomalies(self, anomalies_data: List[Dict]) -> bool:
        """
        Store network anomalies in the database.
        
        Args:
            anomalies_data: List of anomaly data dictionaries
            
        Returns:
            bool: True if storage was successful, False otherwise
        """
        try:
            if not anomalies_data:
                return True  # Nothing to store
                
            # Add storage timestamp
            for anomaly in anomalies_data:
                anomaly["stored_at"] = datetime.now()
            
            # Insert anomalies into collection
            result = self.anomalies_collection.insert_many(anomalies_data)
            
            return len(result.inserted_ids) == len(anomalies_data)
        except Exception as e:
            print(f"Error storing anomalies: {str(e)}")
            return False
    
    def get_latest_metrics(self, limit: int = 100) -> List[Dict]:
        """
        Retrieve the most recent metrics.
        
        Args:
            limit: Maximum number of metrics to retrieve
            
        Returns:
            List of metric documents
        """
        metrics = list(
            self.metrics_collection.find().sort("timestamp", -1).limit(limit)
        )
        
        # Convert ObjectId to string for JSON serialization
        for metric in metrics:
            metric["_id"] = str(metric["_id"])
        
        return metrics
    
    def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
