from pydantic import BaseModel
import json

# Define your Pydantic model
class User(BaseModel):
    id: int
    name: str
    email: str

# Convert the Pydantic model to a JSON schema
user_schema = User.schema()

# Optionally, convert the schema to a JSON string
user_schema_json = json.dumps(user_schema, indent=2)

print(user_schema_json)
