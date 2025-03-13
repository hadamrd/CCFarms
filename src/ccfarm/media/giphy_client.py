import os
import requests
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional

class GifImage(BaseModel):
    """Pydantic model to represent the essential GIF image information from Giphy API."""
    url: HttpUrl = Field(..., description="URL to the original GIF")
    mp4: Optional[HttpUrl] = Field(None, description="URL to MP4 version if available")
    width: str = Field(..., description="Width of the GIF")
    height: str = Field(..., description="Height of the GIF")
    frames: Optional[str] = Field(None, description="Number of frames in the GIF")
    size: Optional[str] = Field(None, description="File size in bytes")

class GiphyClient:
    """Class to download GIFs from Giphy with structured response handling."""
    BASE_URL = "https://api.giphy.com/v1"
    
    def __init__(self, api_key: str|None = None):
        self.api_key = api_key or os.getenv("GIPHY_API_KEY")
        if not self.api_key:
            raise ValueError("GIPHY API key required for GifDownloader")

    def search_gif(self, keyword: str, limit: int = 1) -> List[GifImage]:
        """
        Search for GIFs using a keyword via the GIPHY API.
        
        Args:
            keyword: Search term for finding GIFs
            limit: Maximum number of results to return
            
        Returns:
            List of GifImage objects containing essential GIF information
        """
        url = f"{self.BASE_URL}/gifs/search?api_key={self.api_key}&q={keyword}&limit={limit}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            gif_images = []
            if data.get("data") and len(data["data"]) > 0:
                for gif_data in data["data"]:
                    if "images" in gif_data and "original" in gif_data["images"]:
                        # Directly validate the model using Pydantic
                        try:
                            gif_image = GifImage.model_validate(gif_data["images"]["original"])
                            gif_images.append(gif_image)
                        except Exception as e:
                            print(f"Error validating GIF data: {e}")
                            
            return gif_images
        except requests.RequestException as e:
            print(f"Error searching for GIF with keyword '{keyword}': {e}")
            return []

    def download_gif(self, gif_image: GifImage, path: str) -> bool:
        """
        Download a GIF from the provided GifImage data.
        
        Args:
            gif_image: GifImage object with URL information
            path: Destination file path
            
        Returns:
            Boolean indicating success or failure
        """
        url = str(gif_image.url)
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            with open(path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        
            return os.path.exists(path) and os.path.getsize(path) > 0
        except requests.RequestException as e:
            print(f"Error downloading GIF from {url}: {e}")
            return False

    def download_mp4_if_available(self, gif_image: GifImage, path: str) -> bool:
        """
        Download MP4 version of the GIF if available.
        This can be more efficient and have better compatibility.
        
        Args:
            gif_image: GifImage object with URL information
            path: Destination file path
            
        Returns:
            Boolean indicating success or failure
        """
        if not gif_image.mp4:
            print("No MP4 version available for this GIF")
            return False
            
        url = str(gif_image.mp4)
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            with open(path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        
            return os.path.exists(path) and os.path.getsize(path) > 0
        except requests.RequestException as e:
            print(f"Error downloading MP4 from {url}: {e}")
            return False