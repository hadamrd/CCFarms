#!/usr/bin/env python3
"""
Prefect Block for storing network metrics in MongoDB.
"""

from networking.persistence.metric_storage import MetricsStorage
from prefect.blocks.core import Block
from pydantic import Field

class MetricsStorageBlock(Block):
    """Prefect Block for storing network metrics in MongoDB"""
    
    _block_type_name = "Metrics Storage"
    _block_description = "Store network telemetry metrics in MongoDB"
    _block_type_slug = "metrics-storage"
    _logo_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/MongoDB_Logo.svg/2560px-MongoDB_Logo.svg.png"
    
    connection_string: str = Field(
        ..., 
        description="MongoDB connection string"
    )
    db_name: str = Field(
        default="article_db", 
        description="Database name"
    )
    metrics_collection: str = Field(
        default="metrics", 
        description="Collection name for storing metrics"
    )
    anomalies_collection: str = Field(
        default="anomalies", 
        description="Collection name for storing anomalies"
    )
    
    def get_metrics_storage(self) -> MetricsStorage:
        """
        Get an initialized MetricsStorage instance
        
        Returns:
            Configured MetricsStorage instance
        """
        return MetricsStorage(
            connection_string=self.connection_string,
            database=self.db_name,
            metrics_collection=self.metrics_collection,
            anomalies_collection=self.anomalies_collection
        )
    
    def store_metrics(self, metrics_data):
        """
        Store network metrics directly using this block
        
        Args:
            metrics_data: List of metric dictionaries to store
            
        Returns:
            bool: True if storage was successful
        """
        storage = self.get_metrics_storage()
        result = storage.store_metrics(metrics_data)
        storage.close()
        return result
    
    def store_anomalies(self, anomalies_data):
        """
        Store network anomalies directly using this block
        
        Args:
            anomalies_data: List of anomaly dictionaries to store
            
        Returns:
            bool: True if storage was successful
        """
        storage = self.get_metrics_storage()
        result = storage.store_anomalies(anomalies_data)
        storage.close()
        return result
