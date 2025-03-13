import os
import requests

class UnsplashClient:
    def __init__(self, api_key: str):
        self.api_key = api_key or os.getenv("UNSPLASH_API_KEY")
        self.base_url = "https://api.unsplash.com"

    def search_image(self, query: str, limit: int = 1) -> list[dict]|None:
        """Search for images based on a keyword."""
        url = f"{self.base_url}/search/photos"
        headers = {"Authorization": f"Client-ID {self.api_key}"}
        params = {"query": query, "per_page": limit}
        try:
            response = requests.get(url, headers=headers, params=params) # type: ignore
            response.raise_for_status()
            data = response.json()
            return data.get("results", []) # type: ignore
        except Exception as e:
            print(f"Error searching Unsplash for '{query}': {str(e)}")
            return None

    def download_image(self, image_data: dict, output_path: str) -> bool:
        """Download an image from Unsplash to the specified path."""
        image_url = image_data.get("urls", {}).get("regular")
        if not image_url:
            print("No image URL found in image data")
            return False
        try:
            response = requests.get(image_url, stream=True)
            response.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception as e:
            print(f"Error downloading image to {output_path}: {str(e)}")
            return False