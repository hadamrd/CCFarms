# src/orchestration_play/blocks/brief_storage_block.py
from ccfarm.persistence.brief_storage import BriefStorage
from prefect.blocks.core import Block
from typing import Optional

class BriefStorageBlock(Block):
    """Block for managing BriefStorage connections."""
    
    _block_type_name = "Brief Storage"
    _block_type_slug = "brief-storage"
    _logo_url = "https://image.pngaaa.com/229/5858229-middle.png"
    
    connection_string: Optional[str] = None
    db_name: str = "article_db"
    collection_name: str = "article_briefs"
    
    def get_brief_storage(self) -> BriefStorage:
        """
        Returns an initialized BriefStorage instance.
        
        Returns:
            BriefStorage: A configured BriefStorage instance
        """
        return BriefStorage(
            connection_string=self.connection_string,
            db_name=self.db_name,
            collection_name=self.collection_name
        )
