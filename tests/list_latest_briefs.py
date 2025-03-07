#!/usr/bin/env python3
"""
Script to view the latest article briefs stored in MongoDB.
"""

from pymongo import MongoClient
from datetime import datetime
import json
from tabulate import tabulate
import argparse
import sys

def connect_to_mongodb(connection_string):
    """Establish connection to MongoDB."""
    try:
        client = MongoClient(connection_string)
        # Test connection
        client.admin.command('ping')
        return client
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        sys.exit(1)

def get_latest_briefs(client, db_name, collection_name, limit=10, full_output=False):
    """Retrieve the latest briefs from MongoDB."""
    db = client[db_name]
    collection = db[collection_name]
    
    # Find the latest briefs, sorted by timestamp in descending order
    cursor = collection.find().sort("timestamp", -1).limit(limit)
    
    briefs = []
    for doc in cursor:
        # Convert MongoDB ObjectId to string for JSON serialization
        doc["_id"] = str(doc["_id"])
        
        # Format the timestamp
        if "timestamp" in doc and isinstance(doc["timestamp"], datetime):
            doc["timestamp"] = doc["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
            
        briefs.append(doc)
    
    return briefs

def format_brief_for_display(brief, full_output=False):
    """Format a brief for display in the console."""
    if full_output:
        return json.dumps(brief, indent=2)
    
    # Extract key information for tabular display
    article_id = brief.get("article_id", "N/A")
    timestamp = brief.get("timestamp", "N/A")
    
    # Try to extract title from model output if available
    model_output = brief.get("model_output", {})
    title = "N/A"
    
    # Look for common title fields in model output
    if isinstance(model_output, dict):
        if "title" in model_output:
            title = model_output["title"]
        elif "headline" in model_output:
            title = model_output["headline"]
        elif "summary" in model_output and isinstance(model_output["summary"], dict) and "title" in model_output["summary"]:
            title = model_output["summary"]["title"]
    
    # Truncate title if too long
    if len(title) > 50:
        title = title[:47] + "..."
    
    return {
        "Article ID": article_id,
        "Title": title,
        "Timestamp": timestamp
    }

def main():
    parser = argparse.ArgumentParser(description="View the latest article briefs from MongoDB.")
    parser.add_argument("-l", "--limit", type=int, default=10, help="Maximum number of briefs to display")
    parser.add_argument("-f", "--full", action="store_true", help="Display full brief output")
    parser.add_argument("-c", "--connection", type=str, 
                        default="mongodb://article_user:article_password@localhost:27017/article_db?authSource=admin",
                        help="MongoDB connection string")
    parser.add_argument("-d", "--database", type=str, default="article_db", 
                        help="MongoDB database name")
    parser.add_argument("-n", "--collection", type=str, default="article_briefs", 
                        help="MongoDB collection name")
    
    args = parser.parse_args()
    
    # Connect to MongoDB
    client = connect_to_mongodb(args.connection)
    
    try:
        # Get the latest briefs
        briefs = get_latest_briefs(client, args.database, args.collection, args.limit, args.full)
        
        if not briefs:
            print("No briefs found in the database.")
            return
        
        if args.full:
            # Display full JSON for each brief
            for i, brief in enumerate(briefs, 1):
                print(f"\n=== Brief {i} ===")
                print(json.dumps(brief, indent=2))
        else:
            # Display briefs in a table
            table_data = [format_brief_for_display(brief) for brief in briefs]
            print(tabulate(table_data, headers="keys", tablefmt="pretty"))
            print(f"\nDisplaying {len(briefs)} most recent briefs")
            print(f"For full brief details, use the --full flag")
    
    finally:
        # Close the MongoDB connection
        client.close()

if __name__ == "__main__":
    main()