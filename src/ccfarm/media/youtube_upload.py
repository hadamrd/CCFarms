import json
import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from prefect.blocks.system import Secret

def upload_video_to_youtube(
    video_path: str,
    title: str = "Untitled Video",
    description: str = "Uploaded via Python script",
    tags: list[str] = ["video", "upload"],
    privacy_status: str = "public",
    client_secrets_block: str = "youtube-client-secret",
    credentials_block: str = "youtube-credentials",
    category_id: str = "24"
) -> str|None:
    # Validate video file
    if not os.path.exists(video_path):
        print(f"Error: Video file not found at {video_path}")
        return None
    
    if not video_path.lower().endswith(".mp4"):
        print(f"Warning: {video_path} is not an MP4 file, upload might fail")

    # Load client secrets from Prefect Secret block if not provided
    try:
        client_secrets_str = Secret.load(client_secrets_block).get()
        # If client_secrets is already a dict, use it directly
        if isinstance(client_secrets_str, dict):
            client_secrets = client_secrets_str
        else:
            # Otherwise, try to parse it as JSON
            client_secrets = json.loads(client_secrets_str)
    except Exception as e:
        print(f"Error loading client secrets from Secret block '{client_secrets_block}': {str(e)}")
        return None

    # Validate client secrets
    if not client_secrets or "installed" not in client_secrets:
        print("Error: Invalid client secrets format; must contain 'installed' key")
        return None

    # OAuth 2.0 authentication
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    creds = None

    # Try to load existing credentials from Prefect Secret block
    try:
        creds_data = Secret.load(credentials_block).get()
        # Handle both string and dict formats
        if isinstance(creds_data, dict):
            creds_info = creds_data
        else:
            creds_info = json.loads(creds_data)
        creds = Credentials.from_authorized_user_info(creds_info, scopes)
        print(f"Loaded credentials from Secret block '{credentials_block}'")
    except Exception as e:
        print(f"Could not load credentials from Secret block: {str(e)}")

    # Refresh or obtain new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                # Don't try to update the existing Secret, create a new one
                creds_json = creds.to_json()
                Secret(value=creds_json).save(credentials_block, overwrite=True)  # type: ignore
                print(f"Updated refreshed credentials in Secret block '{credentials_block}'")
            except Exception as e:
                print(f"Warning: Could not update refreshed credentials in Secret block: {str(e)}")
                # Fall back to file-based storage
                with open("~/.creds/youtube_credentials_backup.json", "w") as token_file:
                    token_file.write(creds.to_json())
                print("Saved refreshed credentials to backup file as fallback")
        else:
            try:
                # Need to get new credentials via local OAuth flow
                flow = InstalledAppFlow.from_client_config(client_secrets, scopes)
                creds = flow.run_local_server(port=8081)
                
                # Save new credentials to Secret block
                try:
                    creds_json = creds.to_json()
                    # Use save with overwrite instead of update
                    Secret(value=creds_json).save(credentials_block, overwrite=True)  # type: ignore
                    print(f"Saved new credentials to Secret block '{credentials_block}'")
                except Exception as e:
                    print(f"Warning: Could not save credentials to Secret block: {str(e)}")
                    # Fall back to file-based storage
                    with open("~/.creds/youtube_credentials_backup.json", "w") as token_file:
                        token_file.write(creds.to_json())
                    print("Saved credentials to backup file as fallback")
            except Exception as e:
                print(f"Error during OAuth flow: {str(e)}")
                return None

    try:
        # Build YouTube API service
        youtube = build("youtube", "v3", credentials=creds)

        if not title or not title.strip():
            title = "Untitled Video"
        
        # YouTube has a 100-character limit on titles
        if len(title) > 100:
            print(f"Warning: Title exceeds YouTube's 100-character limit. Truncating from {len(title)} to 100 characters.")
            title = title[:97] + "..."
        
        # Ensure description is not None
        if description is None:
            description = ""
            
        # Ensure tags is a list
        if tags is None:
            tags = []

        # Define video metadata
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False
            },
        }

        # Upload video
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = request.execute()

        video_id = response["id"]
        print(f"Video uploaded successfully. YouTube Video ID: {video_id}")
        return f"https://youtu.be/{video_id}"
    except Exception as e:
        print(f"Error uploading video to YouTube: {str(e)}")
        return None

if __name__ == "__main__":
    video_url = upload_video_to_youtube(
        video_path="/home/kmajdoub/orchestration-play/videos/tiktoks-death-spiral-vs-hard-drive-hoarders-when-your-data-cant-decide-if-its-going-to-the-cloud-or-your-basement.mp4",
        title="TikTok's Death Spiral vs. Hard Drive Hoarders",
        description="A satirical take on the looming TikTok ban and why local storage refuses to die in our cloud-obsessed world. Watch as I roast Silicon Valley's inability to replace a dancing app and the stubborn persistence of physical drives in an era where everything's supposedly in the cloud.",
        tags=[
            "Social Media",
            "TikTok Ban",
            "Data Storage",
            "Cloud Computing",
            "Technology"
        ],
        privacy_status="public"
    )
    if video_url:
        print(f"Video available at: {video_url}")
    else:
        print("Upload failed")