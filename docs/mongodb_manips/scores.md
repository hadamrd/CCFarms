# MongoDB Operations Guide

## Connecting to MongoDB

```bash
docker compose exec mongodb mongosh "mongodb://article_user:article_password@localhost:27017/article_db?authSource=admin"
```

## MongoDB Shell Commands

After connecting to the MongoDB shell, you can perform the following operations:

### 1. View Briefs

```javascript
// Switch to the article database
use article_db

// View the 10 most recent briefs
db.article_briefs.find().sort({timestamp: -1}).limit(10).pretty()

// Count total number of briefs
db.article_briefs.countDocuments()

// Find a specific brief by article_id
db.article_briefs.findOne({article_id: "your-article-id"})
```

### 2. Clean Up Briefs Collection

```javascript
// Switch to the article database
use article_db

// Drop the entire briefs collection
db.article_briefs.drop()

// Create a new empty collection
db.createCollection("article_briefs")

// Create required indexes
db.article_briefs.createIndex({"article_id": 1}, {unique: true})
db.article_briefs.createIndex({"timestamp": 1})
```

### 3. Export Data (Optional)

```javascript
// Export all briefs to a variable for inspection
let allBriefs = db.article_briefs.find().toArray()

// Print the number of briefs
print("Total briefs: " + allBriefs.length)

// Print a specific brief
print(JSON.stringify(allBriefs[0], null, 2))
```

### 4. Exit MongoDB Shell

```javascript
exit
```
