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
    client_secrets: dict|None = None,  # Changed to accept a dict
    client_secrets_block: str = "youtube-client-secret",  # Secret block name
    credentials_file: str = "youtube_credentials.json"
) -> str|None:
    # Validate video file
    if not os.path.exists(video_path):
        print(f"Error: Video file not found at {video_path}")
        return None
    
    if not video_path.lower().endswith(".mp4"):
        print(f"Warning: {video_path} is not an MP4 file, upload might fail")

    # Load client secrets from Prefect Secret block if not provided
    if client_secrets is None:
        try:
            client_secrets = Secret.load(client_secrets_block).get()
            if not isinstance(client_secrets, dict):
                print(f"Error: Client secrets from block '{client_secrets_block}' is not a dictionary")
                return None
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

    # Load existing credentials if available
    if os.path.exists(credentials_file):
        creds = Credentials.from_authorized_user_file(credentials_file, scopes)

    # Refresh or obtain new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            try:
                flow = InstalledAppFlow.from_client_config(client_secrets, scopes)
                creds = flow.run_local_server(port=8081)
                with open(credentials_file, "w") as token_file:
                    token_file.write(creds.to_json())
            except Exception as e:
                print(f"Error during OAuth flow: {str(e)}")
                return None

    try:
        # Build YouTube API service
        youtube = build("youtube", "v3", credentials=creds)

        # Define video metadata
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": "23",  # Comedy category
            },
            "status": {
                "privacyStatus": privacy_status,
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
        video_path="/home/kmajdoub/orchestration-play/combined_output.mp4",
        title="Latest Comedy Compilation",
        description="A fresh batch of AI-generated satirical comedy sketches.",
        tags=["comedy", "satire", "AI"],
        privacy_status="public",
        credentials_file="~/.creds/youtube_credentials.json"
    )
    if video_url:
        print(f"Video available at: {video_url}")
    else:
        print("Upload failed")