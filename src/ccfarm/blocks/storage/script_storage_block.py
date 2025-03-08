from ccfarm.persistence.script_storage import ScriptStorage
from prefect.blocks.core import Block
from pydantic import Field

class ScriptStorageBlock(Block):
    """Prefect Block for storing comedy scripts in MongoDB"""
    
    _block_type_name = "Script Storage"
    _block_description = "Store comedy scripts in MongoDB"
    _block_type_slug = "script-storage"
    _logo_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/MongoDB_Logo.svg/2560px-MongoDB_Logo.svg.png"
    
    connection_string: str = Field(
        ..., 
        description="MongoDB connection string"
    )
    db_name: str = Field(default="article_db", description="Database name")
    collection_name: str = Field(default="comedy_scripts", description="Collection name for scripts")
    
    def get_script_storage(self) -> ScriptStorage:
        """
        Get an initialized ScriptStorage instance
        
        Returns:
            Configured ScriptStorage instance
        """
        return ScriptStorage(
            connection_string=self.connection_string,
            database=self.db_name,
            collection=self.collection_name
        )
