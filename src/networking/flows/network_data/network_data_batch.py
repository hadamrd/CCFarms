#!/usr/bin/env python3
"""
Batch processor for network metrics CSV files.
This script processes CSV files in a directory and stores the data in MongoDB
using a Prefect MetricsStorageBlock.
"""

import os
import shutil
import pandas as pd
from datetime import datetime
from typing import List, Dict

# Import the Prefect metrics storage block
from networking.blocks.metric_storage_block import MetricsStorageBlock

# Configuration
CURDIR = os.path.dirname(os.path.realpath(__file__))

INPUT_DIR = os.path.join(CURDIR, "input")
PROCESSED_DIR = os.path.join(CURDIR, "processed")
ERROR_DIR = os.path.join(CURDIR, "error")
LOG_PATH = os.path.join(CURDIR, "logs", "metrics_processor.log")

# Alert thresholds for anomaly detection
ALERT_THRESHOLDS = {
    "latency_ms": 50.0,           # Alert if latency > 50ms
    "packet_loss_percent": 1.0,   # Alert if packet loss > 1%
    "jitter_ms": 10.0,            # Alert if jitter > 10ms
}

# Name of the storage block to use (configurable at runtime)
DEFAULT_BLOCK_NAME = "dev-metrics-storage"

# Configure logging

print("Network metrics batch processor started")

def ensure_directories():
    """Create necessary directories if they don't exist."""
    for directory in [INPUT_DIR, PROCESSED_DIR, ERROR_DIR]:
        os.makedirs(directory, exist_ok=True)
        print(f"Directory confirmed: {directory}")

def get_csv_files() -> List[str]:
    """
    Get list of CSV files in the input directory.
    
    Returns:
        List of file paths
    """
    files = [
        os.path.join(INPUT_DIR, f) 
        for f in os.listdir(INPUT_DIR) 
        if f.endswith('.csv')
    ]
    print(f"Found {len(files)} CSV files to process")
    return files

def process_csv_file(file_path: str) -> Dict:
    """
    Process a CSV file with network metrics.
    
    Args:
        file_path: Path to the CSV file
        
    Returns:
        Dictionary with processing results
    """
    filename = os.path.basename(file_path)
    print(f"Processing file: {filename}")
    
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
            print(f"File {filename}: {error_msg}")
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
            print(f"Removed {duplicates_removed} duplicate rows from {filename}")
        
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
                        print(
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
        
        print(f"Successfully processed {filename}: {len(metrics)} metrics, {len(anomalies)} anomalies")
        
    except Exception as e:
        error_msg = str(e)
        print(f"Error processing {filename}: {error_msg}")
        result["errors"].append(error_msg)
    
    return result

def move_file(file_path: str, success: bool):
    """
    Move processed file to appropriate directory.
    
    Args:
        file_path: Path to the file
        success: Whether processing was successful
    """
    filename = os.path.basename(file_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Destination directory based on success
    dest_dir = PROCESSED_DIR if success else ERROR_DIR
    
    # Add timestamp to avoid filename collisions
    dest_file = os.path.join(dest_dir, f"{timestamp}_{filename}")
    
    # Move the file
    shutil.move(file_path, dest_file)
    print(f"Moved {filename} to {dest_dir}")

def process_all_files(block_name: str = DEFAULT_BLOCK_NAME) -> Dict:
    """
    Process all CSV files in the input directory using the specified metrics storage block.
    
    Args:
        block_name: Name of the registered MetricsStorageBlock to use
        
    Returns:
        Dictionary with processing summary
    """
    # Load the storage block
    try:
        print(f"Loading metrics storage block: {block_name}")
        metrics_storage_block = MetricsStorageBlock.load(block_name)
        print(f"Successfully loaded metrics storage block: {block_name}")
    except Exception as e:
        error_msg = f"Failed to load metrics storage block '{block_name}': {str(e)}"
        print(error_msg)
        return {"error": error_msg}
    
    csv_files = get_csv_files()
    
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
    
    if not csv_files:
        print("No CSV files found to process")
        summary["end_time"] = datetime.now().isoformat()
        return summary
    
    for file_path in csv_files:
        # Process the file
        result = process_csv_file(file_path)
        
        if result["success"]:
            # Store metrics using the storage block
            if result["metrics"]:
                try:
                    # Using direct store_metrics method on the block
                    metrics_stored = metrics_storage_block.store_metrics(result["metrics"])
                    if not metrics_stored:
                        print(f"Failed to store metrics for {result['file']}")
                        result["success"] = False
                        result["errors"].append("Failed to store metrics in MongoDB")
                except Exception as e:
                    print(f"Error storing metrics for {result['file']}: {str(e)}")
                    result["success"] = False
                    result["errors"].append(f"Storage error: {str(e)}")
            
            # Store anomalies using the storage block
            if result["anomalies"]:
                try:
                    # Using direct store_anomalies method on the block
                    anomalies_stored = metrics_storage_block.store_anomalies(result["anomalies"])
                    if not anomalies_stored:
                        print(f"Failed to store anomalies for {result['file']}")
                except Exception as e:
                    print(f"Error storing anomalies for {result['file']}: {str(e)}")
        
        # Update summary
        if result["success"]:
            summary["successful_files"] += 1
            summary["total_metrics"] += result.get("row_count", 0)
            summary["total_anomalies"] += result.get("anomaly_count", 0)
        else:
            summary["failed_files"] += 1
            summary["errors"].extend([f"{result['file']}: {err}" for err in result["errors"]])
        
        # Move the file to processed or error directory
        move_file(file_path, result["success"])
    
    summary["end_time"] = datetime.now().isoformat()
    
    # Log summary
    print(f"Processing complete: {summary['successful_files']} files successful, "
                f"{summary['failed_files']} files failed")
    print(f"Total metrics stored: {summary['total_metrics']}")
    print(f"Total anomalies detected: {summary['total_anomalies']}")
    
    return summary

def main(block_name: str = DEFAULT_BLOCK_NAME):
    """
    Main function to run the batch processor.
    
    Args:
        block_name: Name of the registered MetricsStorageBlock to use
    """
    print(f"Starting network metrics batch processor using block: {block_name}")
    
    # Ensure directories exist
    ensure_directories()
    
    try:
        # Process all files using the specified block
        summary = process_all_files(block_name)
        
        print("Batch processing completed successfully")
        return summary
    
    except Exception as e:
        print(f"Error in batch processing: {str(e)}")
        return {"error": str(e)}

if __name__ == "__main__":
    import sys
    
    # Check if block name is provided as command line argument
    if len(sys.argv) > 1:
        block_name = sys.argv[1]
    else:
        block_name = DEFAULT_BLOCK_NAME
    
    main(block_name)
    