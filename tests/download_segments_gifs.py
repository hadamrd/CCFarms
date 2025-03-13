import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Load GIPHY API key
giphy_api_key = os.getenv("GIPHY_API_KEY")

def search_gif(keyword, api_key):
    """Search for a GIF using a single keyword via the GIPHY API."""
    url = f"https://api.giphy.com/v1/gifs/search?api_key={api_key}&q={keyword}&limit=1"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        data = response.json()
        
        # Check if we got valid results
        if not data.get("data") or len(data["data"]) == 0:
            print(f"No results found for keyword: '{keyword}'")
            return None
        
        # Get the correct URL for the original GIF
        if "images" in data["data"][0] and "original" in data["data"][0]["images"]:
            return data["data"][0]["images"]["original"]["url"]
        else:
            print(f"Unexpected API response structure for keyword: '{keyword}'")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"API request error for keyword '{keyword}': {str(e)}")
        return None
    except Exception as e:
        print(f"Unexpected error during API search for keyword '{keyword}': {str(e)}")
        return None

def download_gif(url, path):
    """Download a GIF to the specified path."""
    try:
        print(f"Downloading from: {url}")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Write to file
        with open(path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        # Verify file was created and has content
        if os.path.exists(path) and os.path.getsize(path) > 0:
            print(f"Successfully downloaded GIF to: {path}")
            print(f"File size: {os.path.getsize(path) / 1024:.2f} KB")
            return True
        else:
            print(f"File download failed or file is empty")
            return False
            
    except Exception as e:
        print(f"Error during download: {str(e)}")
        return False

def download_segment_gifs(metadata_path, output_dir=None):
    """Download individual GIFs for each keyword in all segments."""
    # Load metadata
    try:
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
        print(f"Successfully loaded metadata from: {metadata_path}")
    except Exception as e:
        print(f"Error loading metadata: {str(e)}")
        return False
    
    # Get segments
    segments = metadata.get("segments", [])
    if not segments:
        print("No segments found in metadata")
        return False
    
    print(f"Found {len(segments)} segments in metadata")
    
    # Use metadata directory if output_dir not specified
    if output_dir is None:
        output_dir = os.path.dirname(metadata_path)
    
    # Create a directory for GIFs
    gifs_dir = os.path.join(output_dir, "gifs")
    os.makedirs(gifs_dir, exist_ok=True)
    print(f"GIFs will be saved to: {gifs_dir}")
    
    # Track results
    successful_downloads = 0
    failed_downloads = 0
    skipped_existing = 0
    
    # Process each segment
    for segment_idx, segment in enumerate(segments):
        segment_number = segment_idx + 1
        print(f"\n--- Processing segment {segment_number}/{len(segments)} ---")
        
        # Check if segment has keywords
        keywords = segment.get("keywords", [])
        if not keywords:
            print(f"No keywords found for segment {segment_number}, skipping")
            continue
        
        print(f"Found {len(keywords)} keywords: {keywords}")
        
        # Process each keyword individually
        for keyword_idx, keyword in enumerate(keywords):
            keyword_number = keyword_idx + 1
            print(f"\nProcessing keyword {keyword_number}/{len(keywords)}: '{keyword}'")
            
            # Create filename for this keyword's GIF
            safe_keyword = keyword.lower().replace(" ", "_")
            gif_filename = f"segment{segment_number:02d}_keyword{keyword_number:02d}_{safe_keyword}.gif"
            gif_path = os.path.join(gifs_dir, gif_filename)
            
            # Check if we already have this GIF
            if os.path.exists(gif_path) and os.path.getsize(gif_path) > 0:
                print(f"GIF already exists: {gif_path}")
                skipped_existing += 1
                continue
            
            # Search for GIF using this single keyword
            gif_url = search_gif(keyword, giphy_api_key)
            if not gif_url:
                print(f"Failed to get GIF URL for keyword '{keyword}'")
                failed_downloads += 1
                continue
            
            # Download GIF
            success = download_gif(gif_url, gif_path)
            if success:
                successful_downloads += 1
            else:
                failed_downloads += 1
                # Remove failed download if file was created
                if os.path.exists(gif_path):
                    try:
                        os.remove(gif_path)
                        print(f"Removed incomplete download: {gif_path}")
                    except:
                        pass
    
    # Print summary
    print("\n=== Download Summary ===")
    total_keywords = sum(len(segment.get("keywords", [])) for segment in segments)
    print(f"Total segments: {len(segments)}")
    print(f"Total keywords: {total_keywords}")
    print(f"Successfully downloaded: {successful_downloads}")
    print(f"Failed downloads: {failed_downloads}")
    print(f"Skipped (already exist): {skipped_existing}")
    
    return successful_downloads > 0

def main():
    import sys
    
    if len(sys.argv) > 1:
        metadata_path = sys.argv[1]
        output_dir = None
        
        # Check for optional output directory
        if len(sys.argv) > 2:
            output_dir = sys.argv[2]
    else:
        # Use default path for testing
        metadata_path = input("Enter path to metadata JSON file: ")
        output_dir = None
    
    if not os.path.exists(metadata_path):
        print(f"Error: Metadata file not found at {metadata_path}")
        return
        
    print(f"Starting GIF download for metadata: {metadata_path}")
    result = download_segment_gifs(metadata_path, output_dir)
    
    if result:
        print("\nGIF download process completed successfully")
    else:
        print("\nGIF download process completed with errors")

if __name__ == "__main__":
    main()