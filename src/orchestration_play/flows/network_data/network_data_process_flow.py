#!/usr/bin/env python3
"""
Batch processor for network metrics CSV files as a Prefect pipeline.
This script processes CSV files in a directory and stores the data in MongoDB.
Uses standard CSV module instead of Pandas and sends Teams notifications.
"""

import os
import csv
import shutil
import json
from datetime import datetime
from typing import List, Dict

from orchestration_play.blocks.notifications.teams_webhook import TeamsWebhook
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
# Teams webhook block name
TEAMS_WEBHOOK_BLOCK = "weather-teams-webhook"

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

@task
def load_teams_webhook():
    """
    Load the Teams webhook notification block.
    
    Returns:
        Loaded Teams webhook block
    """
    logger = get_run_logger()
    logger.info(f"Loading Teams webhook block: {TEAMS_WEBHOOK_BLOCK}")
    
    try:
        teams_block = TeamsWebhook.load(TEAMS_WEBHOOK_BLOCK)
        logger.info(f"Successfully loaded Teams webhook block")
        return teams_block
    except Exception as e:
        logger.error(f"Failed to load Teams webhook block: {str(e)}")
        logger.warning("Continuing without Teams notifications")
        return None

@task
def notify_teams(teams_block, message, title=None):
    """Send notification to Teams."""
    if not teams_block:
        return False
    
    logger = get_run_logger()
    try:
        teams_block.notify(message)
        logger.info(f"Teams notification sent: {message[:100]}...")
        return True
    except Exception as e:
        logger.error(f"Failed to send Teams notification: {str(e)}")
        return False

@task(retries=2)
def process_csv_file(file_path: str, teams_block) -> Dict:
    """
    Process a CSV file with network metrics using standard CSV module.
    
    Args:
        file_path: Path to the CSV file
        teams_block: Teams webhook for notifications
        
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
        # Required columns
        required_columns = [
            "timestamp", "device_id", "latency_ms", 
            "packet_loss_percent", "bandwidth_mbps", 
            "jitter_ms", "signal_strength_dbm"
        ]
        
        # Process the CSV file
        metrics = []
        anomalies = []
        duplicates = set()  # Track duplicates
        
        with open(file_path, 'r', newline='') as csvfile:
            # Read header
            reader = csv.DictReader(csvfile)
            
            # Validate columns
            missing_columns = [col for col in required_columns if col not in reader.fieldnames]
            if missing_columns:
                error_msg = f"Missing columns: {', '.join(missing_columns)}"
                logger.error(f"File {filename}: {error_msg}")
                result["errors"].append(error_msg)
                
                # Send Teams notification for missing columns
                if teams_block:
                    notify_teams(
                        teams_block,
                        f"⚠️ Error in file {filename}: {error_msg}"
                    )
                return result
            
            # Process rows
            for row in reader:
                # Skip if any required column is empty
                if any(not row.get(col) for col in required_columns):
                    continue
                
                # Create a unique key for duplicate detection
                row_key = f"{row['timestamp']}_{row['device_id']}"
                if row_key in duplicates:
                    continue
                duplicates.add(row_key)
                
                # Convert string values to appropriate types
                try:
                    # Convert numeric values
                    for key in row:
                        if key in ["latency_ms", "packet_loss_percent", "bandwidth_mbps", 
                                  "jitter_ms", "signal_strength_dbm"]:
                            row[key] = float(row[key])
                    
                    # Check for anomalies
                    for metric, threshold in ALERT_THRESHOLDS.items():
                        if metric in row and float(row[metric]) > threshold:
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
                            
                            # Send Teams notification for anomaly
                            if teams_block:
                                notify_teams(
                                    teams_block,
                                    f"🚨 Anomaly detected: Device {row['device_id']} has {metric}={row[metric]} (threshold: {threshold})"
                                )
                    
                    # Add to metrics list
                    metrics.append(row)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Skipping row with invalid data: {str(e)}")
        
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
        
        # Send Teams notification for processing error
        if teams_block:
            notify_teams(
                teams_block,
                f"🔥 Error processing file {filename}: {error_msg[:200]}"
            )
    
    return result

@task(retries=2)
def store_metrics(metrics_storage_block, metrics, filename, teams_block):
    """
    Store metrics in MongoDB.
    
    Args:
        metrics_storage_block: The storage block to use
        metrics: List of metrics to store
        filename: Source filename for error reporting
        teams_block: Teams webhook for notifications
        
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
            error_msg = f"Failed to store metrics for {filename}"
            logger.error(error_msg)
            
            # Send Teams notification
            if teams_block:
                notify_teams(
                    teams_block,
                    f"❌ {error_msg}"
                )
            return False
    except Exception as e:
        error_msg = f"Error storing metrics for {filename}: {str(e)}"
        logger.error(error_msg)
        
        # Send Teams notification
        if teams_block:
            notify_teams(
                teams_block,
                f"❌ {error_msg[:200]}"
            )
        return False

@task(retries=2)
def store_anomalies(metrics_storage_block, anomalies, filename, teams_block):
    """
    Store anomalies in MongoDB.
    
    Args:
        metrics_storage_block: The storage block to use
        anomalies: List of anomalies to store
        filename: Source filename for error reporting
        teams_block: Teams webhook for notifications
        
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
            warning_msg = f"Failed to store anomalies for {filename}"
            logger.warning(warning_msg)
            
            # Send Teams notification
            if teams_block:
                notify_teams(
                    teams_block,
                    f"⚠️ {warning_msg}"
                )
            return False
    except Exception as e:
        warning_msg = f"Error storing anomalies for {filename}: {str(e)}"
        logger.warning(warning_msg)
        
        # Send Teams notification
        if teams_block:
            notify_teams(
                teams_block,
                f"⚠️ {warning_msg[:200]}"
            )
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
    
    # Load Teams webhook
    teams_block = load_teams_webhook()
    
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
    
    # Send initial notification
    if teams_block:
        notify_teams(
            teams_block,
            f"🔄 Starting network metrics processing for {len(csv_files)} files"
        )
    
    for file_path in csv_files:
        # Process the file
        result = process_csv_file(file_path, teams_block)
        
        file_success = result["success"]
        
        # Store metrics and anomalies if processing was successful
        if file_success:
            # Store metrics
            if result["metrics"]:
                metrics_stored = store_metrics(
                    metrics_storage_block, 
                    result["metrics"], 
                    result["file"],
                    teams_block
                )
                
                if not metrics_stored:
                    file_success = False
                    result["errors"].append("Failed to store metrics in MongoDB")
            
            # Store anomalies
            if result["anomalies"]:
                store_anomalies(
                    metrics_storage_block, 
                    result["anomalies"], 
                    result["file"],
                    teams_block
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
    
    # Send completion notification to Teams
    if teams_block:
        status_emoji = "✅" if summary["failed_files"] == 0 else "⚠️"
        notify_teams(
            teams_block,
            f"{status_emoji} Network metrics processing complete:\n"
            f"• Processed: {summary['total_files']} files\n"
            f"• Successful: {summary['successful_files']} files\n"
            f"• Failed: {summary['failed_files']} files\n"
            f"• Metrics stored: {summary['total_metrics']}\n"
            f"• Anomalies detected: {summary['total_anomalies']}"
        )
        
        # Send errors report if any
        if summary["errors"]:
            errors_message = "🔥 Errors encountered:\n• " + "\n• ".join(summary["errors"][:10])
            if len(summary["errors"]) > 10:
                errors_message += f"\n...and {len(summary['errors']) - 10} more errors"
            
            notify_teams(teams_block, errors_message)
    
    return summary

# Script entrypoint
if __name__ == "__main__":
    process_metrics_pipeline(DEFAULT_BLOCK_NAME)