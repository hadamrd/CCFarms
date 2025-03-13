import os
import requests
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import webbrowser
import urllib.parse
import socket
import time

# Step 1: Configuration - Replace these with your LinkedIn App credentials
CLIENT_ID = os.getenv('LINKEDIN_CLIENT_ID')
CLIENT_SECRET = os.getenv('LINKEDIN_CLIENT_SECRET')

# Function to find an available port
def find_available_port(start_port=8000, max_port=8100):
    for port in range(start_port, max_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('localhost', port))
                return port
            except OSError:
                continue
    raise RuntimeError("Could not find an available port")

# Find an available port and set redirect URI
PORT = find_available_port()
REDIRECT_URI = f'http://localhost:{PORT}/callback'

# Step 2: OAuth 2.0 Authentication Flow
def get_authorization_url():
    auth_url = 'https://www.linkedin.com/oauth/v2/authorization'
    params = {
        'response_type': 'code',
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'scope': 'w_member_social',  # Scope for posting content
        'state': 'random_state_string'  # For CSRF protection
    }
    return auth_url + '?' + urllib.parse.urlencode(params)

# Global variable to store the authorization code
AUTH_CODE = None

# Step 3: Handle the callback and get access token
class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global AUTH_CODE
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        # Extract authorization code from URL
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        
        if 'code' in params:
            AUTH_CODE = params['code'][0]
            self.wfile.write(b"<html><body><h1>Authentication successful!</h1><p>You can close this window now.</p></body></html>")
        else:
            self.wfile.write(b"<html><body><h1>Authentication failed!</h1><p>No code parameter found.</p></body></html>")
    
    def log_message(self, format, *args):
        # Silence server logs
        return

def get_access_token(code):
    token_url = 'https://www.linkedin.com/oauth/v2/accessToken'
    payload = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    
    try:
        response = requests.post(token_url, data=payload)
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        return response.json().get('access_token')
    except requests.exceptions.RequestException as e:
        print(f"Failed to get access token: {e}")
        if hasattr(e, 'response'):
            print(f"Response status: {e.response.status_code}")
            print(f"Response text: {e.response.text}")
        return None

# Step 4: Make a LinkedIn Post
def make_linkedin_post(access_token, post_text="Hello from my Python script! This is an automated post."):
    # Get your LinkedIn URN
    me_url = 'https://api.linkedin.com/v2/me'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'X-Restli-Protocol-Version': '2.0.0'  # Important for LinkedIn API
    }
    
    try:
        me_response = requests.get(me_url, headers=headers)
        me_response.raise_for_status()
        
        person_urn = me_response.json()['id']
        author = f'urn:li:person:{person_urn}'
        
        # Create the post
        post_url = 'https://api.linkedin.com/v2/ugcPosts'
        post_data = {
            'author': author,
            'lifecycleState': 'PUBLISHED',
            'specificContent': {
                'com.linkedin.ugc.ShareContent': {
                    'shareCommentary': {
                        'text': post_text
                    },
                    'shareMediaCategory': 'NONE'
                }
            },
            'visibility': {
                'com.linkedin.ugc.MemberNetworkVisibility': 'PUBLIC'
            }
        }
        
        response = requests.post(post_url, headers=headers, json=post_data)
        response.raise_for_status()
        print("Post created successfully!")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        if hasattr(e, 'response'):
            print(f"Response status: {e.response.status_code}")
            print(f"Response text: {e.response.text}")
        return False

# Step 5: Start the authentication process
def authenticate_and_post(post_text=None):
    if not CLIENT_ID or not CLIENT_SECRET:
        print("Error: LinkedIn credentials not found.")
        print("Please set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET environment variables.")
        return False
    
    # Start a simple server to handle the callback
    server = HTTPServer(('localhost', PORT), CallbackHandler)
    print(f"Starting server on port {PORT}")
    
    # Start server in a separate thread
    import threading
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    # Open browser for authentication
    auth_url = get_authorization_url()
    print(f"Opening browser for authentication using redirect URI: {REDIRECT_URI}")
    webbrowser.open(auth_url)
    
    # Wait for the authentication code
    print("Waiting for authentication...")
    timeout = 120  # seconds
    start_time = time.time()
    
    while AUTH_CODE is None:
        time.sleep(1)
        if time.time() - start_time > timeout:
            print("Timeout waiting for authentication.")
            server.shutdown()
            return False
    
    # Shutdown the server
    server.shutdown()
    print("Authentication code received!")
    
    # Get access token
    access_token = get_access_token(AUTH_CODE)
    if access_token:
        print("Access token obtained successfully!")
        
        # Make the post
        default_text = "Hello from my Python script! This is an automated post."
        return make_linkedin_post(access_token, post_text or default_text)
    else:
        print("Failed to get access token.")
        return False

if __name__ == '__main__':
    # Example usage
    post_text = input("Enter your post text (or press Enter for default message): ").strip()
    authenticate_and_post(post_text if post_text else None)