#!/usr/bin/env python3
"""
Batch processor for network metrics CSV files as a Prefect pipeline.
This script processes CSV files in a directory and stores the data in MongoDB.
"""

import os
import shutil
import pandas as pd
from datetime import datetime
from typing import List, Dict

from prefect import flow, task
from prefect.logging import get_run_logger

# Import the Prefect metrics storage block
from orchestration_play.blocks.storage.metric_storage_block import MetricsStorageBlock

# Configuration
CURDIR = os.path.dirname(os.path.realpath(__file__))

INPUT_DIR = os.path.join(CURDIR, "input")
PROCESSED_DIR = os.path.join(CURDIR, "processed")
ERROR_DIR = os.path.join(CURDIR, "error")

# Alert thresholds for anomaly detection
ALERT_THRESHOLDS = {
    "latency_ms": 50.0,           # Alert if latency > 50ms
    "packet_loss_percent": 1.0,   # Alert if packet loss > 1%
    "jitter_ms": 10.0,            # Alert if jitter > 10ms
}

# Default storage block name
DEFAULT_BLOCK_NAME = "dev-metrics-storage"

@task
def ensure_directories():
    """Create necessary directories if they don't exist."""
    logger = get_run_logger()
    for directory in [INPUT_DIR, PROCESSED_DIR, ERROR_DIR]:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"Directory confirmed: {directory}")

@task
def get_csv_files() -> List[str]:
    """
    Get list of CSV files in the input directory.
    
    Returns:
        List of file paths
    """
    logger = get_run_logger()
    files = [
        os.path.join(INPUT_DIR, f) 
        for f in os.listdir(INPUT_DIR) 
        if f.endswith('.csv')
    ]
    logger.info(f"Found {len(files)} CSV files to process")
    return files

@task
def load_storage_block(block_name: str):
    """
    Load the metrics storage block.
    
    Args:
        block_name: Name of the registered storage block
    
    Returns:
        Loaded storage block
    """
    logger = get_run_logger()
    logger.info(f"Loading metrics storage block: {block_name}")
    
    try:
        metrics_storage_block = MetricsStorageBlock.load(block_name)
        logger.info(f"Successfully loaded metrics storage block: {block_name}")
        return metrics_storage_block
    except Exception as e:
        logger.error(f"Failed to load metrics storage block '{block_name}': {str(e)}")
        raise

@task(retries=2)
def process_csv_file(file_path: str) -> Dict:
    """
    Process a CSV file with network metrics.
    
    Args:
        file_path: Path to the CSV file
        
    Returns:
        Dictionary with processing results
    """
    logger = get_run_logger()
    filename = os.path.basename(file_path)
    logger.info(f"Processing file: {filename}")
    
    result = {
        "file": filename,
        "success": False,
        "metrics": [],
        "anomalies": [],
        "errors": []
    }
    
    try:
        # Read CSV file
        df = pd.read_csv(file_path)
        
        # Validate required columns
        required_columns = [
            "timestamp", "device_id", "latency_ms", 
            "packet_loss_percent", "bandwidth_mbps", 
            "jitter_ms", "signal_strength_dbm"
        ]
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            error_msg = f"Missing columns: {', '.join(missing_columns)}"
            logger.error(f"File {filename}: {error_msg}")
            result["errors"].append(error_msg)
            return result
        
        # Basic data cleaning
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Remove duplicates
        initial_count = len(df)
        df.drop_duplicates(inplace=True)
        duplicates_removed = initial_count - len(df)
        if duplicates_removed > 0:
            logger.info(f"Removed {duplicates_removed} duplicate rows from {filename}")
        
        # Handle missing values
        df.dropna(inplace=True)
        
        # Detect anomalies
        anomalies = []
        for metric, threshold in ALERT_THRESHOLDS.items():
            if metric in df.columns:
                anomalous_rows = df[df[metric] > threshold]
                if not anomalous_rows.empty:
                    for _, row in anomalous_rows.iterrows():
                        anomaly = {
                            "timestamp": row["timestamp"],
                            "device_id": row["device_id"],
                            "metric": metric,
                            "value": float(row[metric]),
                            "threshold": threshold
                        }
                        anomalies.append(anomaly)
                        logger.warning(
                            f"Anomaly in {filename}: {row['device_id']} "
                            f"{metric}={row[metric]} (threshold: {threshold})"
                        )
        
        # Prepare metrics data
        metrics = df.to_dict('records')
        
        # Update result
        result["success"] = True
        result["metrics"] = metrics
        result["anomalies"] = anomalies
        result["row_count"] = len(metrics)
        result["anomaly_count"] = len(anomalies)
        
        logger.info(f"Successfully processed {filename}: {len(metrics)} metrics, {len(anomalies)} anomalies")
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error processing {filename}: {error_msg}")
        result["errors"].append(error_msg)
    
    return result

@task(retries=2)
def store_metrics(metrics_storage_block, metrics, filename):
    """
    Store metrics in MongoDB.
    
    Args:
        metrics_storage_block: The storage block to use
        metrics: List of metrics to store
        filename: Source filename for error reporting
        
    Returns:
        Success status
    """
    logger = get_run_logger()
    
    if not metrics:
        logger.info(f"No metrics to store for {filename}")
        return True
    
    try:
        logger.info(f"Storing {len(metrics)} metrics for {filename}")
        metrics_stored = metrics_storage_block.store_metrics(metrics)
        
        if metrics_stored:
            logger.info(f"Successfully stored metrics for {filename}")
            return True
        else:
            logger.error(f"Failed to store metrics for {filename}")
            return False
    except Exception as e:
        logger.error(f"Error storing metrics for {filename}: {str(e)}")
        return False

@task(retries=2)
def store_anomalies(metrics_storage_block, anomalies, filename):
    """
    Store anomalies in MongoDB.
    
    Args:
        metrics_storage_block: The storage block to use
        anomalies: List of anomalies to store
        filename: Source filename for error reporting
        
    Returns:
        Success status
    """
    logger = get_run_logger()
    
    if not anomalies:
        logger.info(f"No anomalies to store for {filename}")
        return True
    
    try:
        logger.info(f"Storing {len(anomalies)} anomalies for {filename}")
        anomalies_stored = metrics_storage_block.store_anomalies(anomalies)
        
        if anomalies_stored:
            logger.info(f"Successfully stored anomalies for {filename}")
            return True
        else:
            logger.warning(f"Failed to store anomalies for {filename}")
            return False
    except Exception as e:
        logger.warning(f"Error storing anomalies for {filename}: {str(e)}")
        return False

@task
def move_file(file_path: str, success: bool):
    """
    Move processed file to appropriate directory.
    
    Args:
        file_path: Path to the file
        success: Whether processing was successful
    """
    logger = get_run_logger()
    filename = os.path.basename(file_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Destination directory based on success
    dest_dir = PROCESSED_DIR if success else ERROR_DIR
    
    # Add timestamp to avoid filename collisions
    dest_file = os.path.join(dest_dir, f"{timestamp}_{filename}")
    
    # Move the file
    shutil.move(file_path, dest_file)
    logger.info(f"Moved {filename} to {dest_dir}")
    
    return dest_file

@flow(name="Network Metrics Processor")
def process_metrics_pipeline(block_name: str = DEFAULT_BLOCK_NAME):
    """
    Main flow to process network metrics files.
    
    Args:
        block_name: Name of the registered MetricsStorageBlock to use
    """
    logger = get_run_logger()
    logger.info(f"Starting network metrics batch processor using block: {block_name}")
    
    # Ensure directories exist
    ensure_directories()
    
    # Load the storage block
    metrics_storage_block = load_storage_block(block_name)
    
    # Get the list of CSV files
    csv_files = get_csv_files()
    
    if not csv_files:
        logger.info("No CSV files found to process")
        return {
            "status": "success",
            "total_files": 0,
            "message": "No files to process"
        }
    
    # Process each file
    summary = {
        "total_files": len(csv_files),
        "successful_files": 0,
        "failed_files": 0,
        "total_metrics": 0,
        "total_anomalies": 0,
        "errors": [],
        "start_time": datetime.now().isoformat(),
        "end_time": None,
        "storage_block": block_name
    }
    
    for file_path in csv_files:
        # Process the file
        result = process_csv_file(file_path)
        
        file_success = result["success"]
        
        # Store metrics and anomalies if processing was successful
        if file_success:
            # Store metrics
            if result["metrics"]:
                metrics_stored = store_metrics(
                    metrics_storage_block, 
                    result["metrics"], 
                    result["file"]
                )
                
                if not metrics_stored:
                    file_success = False
                    result["errors"].append("Failed to store metrics in MongoDB")
            
            # Store anomalies
            if result["anomalies"]:
                store_anomalies(
                    metrics_storage_block, 
                    result["anomalies"], 
                    result["file"]
                )
        
        # Move the file
        move_file(file_path, file_success)
        
        # Update summary
        if file_success:
            summary["successful_files"] += 1
            summary["total_metrics"] += result.get("row_count", 0)
            summary["total_anomalies"] += result.get("anomaly_count", 0)
        else:
            summary["failed_files"] += 1
            summary["errors"].extend([f"{result['file']}: {err}" for err in result.get("errors", [])])
    
    summary["end_time"] = datetime.now().isoformat()
    
    # Log summary
    logger.info(f"Processing complete: {summary['successful_files']} files successful, "
                f"{summary['failed_files']} files failed")
    logger.info(f"Total metrics stored: {summary['total_metrics']}")
    logger.info(f"Total anomalies detected: {summary['total_anomalies']}")
    
    return summary

# Script entrypoint
if __name__ == "__main__":
    process_metrics_pipeline(DEFAULT_BLOCK_NAME)
