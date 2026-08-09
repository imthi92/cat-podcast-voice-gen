#!/usr/bin/env python3
"""
YouTube Upload Automation - Cat Podcast
Uploads video to YouTube with metadata, tags, and thumbnail.
"""

import os
import sys
import json
import pickle
from datetime import datetime
from pathlib import Path

# YouTube API imports
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    HAS_YT_API = True
except ImportError:
    HAS_YT_API = False
    print("YouTube API not installed. Installing...")
    os.system("pip install google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2")

# ============================================================
# CONFIGURATION
# ============================================================

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRETS_FILE = "client_secret.json"  # Download from Google Cloud Console
TOKEN_FILE = "youtube_token.pickle"

# Default upload settings
DEFAULT_CONFIG = {
    "category_id": "24",  # Entertainment
    "privacy_status": "private",  # Start as private, change to public later
    "default_language": "en",
    "embeddable": True,
    "public_stats_viewable": True,
}

# Tags for discoverability
DEFAULT_TAGS = [
    "cat podcast",
    "funny cats",
    "office cats",
    "cat comedy",
    "simba and meow",
    "cat dialogue",
    "funny cat videos",
    "cat humor",
    "office humor",
    "podcast cats",
    "cat talking",
    "cat personality",
    "funny animals",
    "cat entertainment",
    "cat show",
]


# ============================================================
# AUTHENTICATION
# ============================================================

def get_youtube_service():
    """Authenticate and return YouTube API service."""
    if not HAS_YT_API:
        print("ERROR: YouTube API libraries not installed")
        return None

    credentials = None

    # Check for saved token
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            credentials = pickle.load(token)

    # Refresh or get new credentials
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                print(f"ERROR: {CLIENT_SECRETS_FILE} not found!")
                print("\nTo get this file:")
                print("1. Go to https://console.cloud.google.com")
                print("2. Create project (or select existing)")
                print("3. Enable YouTube Data API v3")
                print("4. Create OAuth 2.0 credentials")
                print("5. Download client_secret.json")
                print("6. Place in this directory")
                return None

            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            credentials = flow.run_local_server(port=0)

        # Save token for next run
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(credentials, token)

    return build('youtube', 'v3', credentials=credentials)


# ============================================================
# UPLOAD FUNCTION
# ============================================================

def upload_video(
    video_path,
    title,
    description,
    tags=None,
    category_id=None,
    privacy_status=None,
    thumbnail_path=None,
    playlist_id=None,
):
    """Upload video to YouTube."""
    print("\n" + "=" * 60)
    print("YOUTUBE UPLOAD")
    print("=" * 60)

    youtube = get_youtube_service()
    if not youtube:
        return None

    # Use defaults if not specified
    if tags is None:
        tags = DEFAULT_TAGS
    if category_id is None:
        category_id = DEFAULT_CONFIG["category_id"]
    if privacy_status is None:
        privacy_status = DEFAULT_CONFIG["privacy_status"]

    # Add episode-specific tags
    title_tags = title.lower().split()
    tags = tags + [t for t in title_tags if len(t) > 3]

    # Prepare upload metadata
    body = {
        "snippet": {
            "title": title[:100],  # YouTube max 100 chars
            "description": description[:5000],  # YouTube max 5000 chars
            "tags": tags[:500],  # YouTube max 500 tags
            "categoryId": category_id,
            "defaultLanguage": DEFAULT_CONFIG["default_language"],
        },
        "status": {
            "privacyStatus": privacy_status,
            "embeddable": DEFAULT_CONFIG["embeddable"],
            "publicStatsViewable": DEFAULT_CONFIG["public_stats_viewable"],
            "selfDeclaredMadeForKids": False,
        },
    }

    print(f"\nUploading: {title}")
    print(f"Video: {video_path}")
    print(f"Privacy: {privacy_status}")

    # Create media upload object
    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=10 * 1024 * 1024,  # 10MB chunks
    )

    # Execute upload
    insert_request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    retry_count = 0
    max_retries = 3

    while response is None:
        try:
            status, response = insert_request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                print(f"  Upload progress: {progress}%")
        except Exception as e:
            if retry_count < max_retries:
                retry_count += 1
                print(f"  Retrying ({retry_count}/{max_retries})...")
                import time
                time.sleep(2 ** retry_count)
            else:
                print(f"  Upload failed: {e}")
                return None

    video_id = response["id"]
    print(f"\n  Video uploaded successfully!")
    print(f"  Video ID: {video_id}")
    print(f"  URL: https://www.youtube.com/watch?v={video_id}")

    # Upload thumbnail
    if thumbnail_path and os.path.exists(thumbnail_path):
        print("\n  Uploading thumbnail...")
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path, mimetype="image/png"),
            ).execute()
            print("  Thumbnail uploaded!")
        except Exception as e:
            print(f"  Thumbnail upload failed: {e}")

    # Add to playlist
    if playlist_id:
        print("\n  Adding to playlist...")
        try:
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": video_id,
                        },
                    }
                },
            ).execute()
            print("  Added to playlist!")
        except Exception as e:
            print(f"  Playlist addition failed: {e}")

    return {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "title": title,
        "privacy": privacy_status,
    }


# ============================================================
# METADATA GENERATION
# ============================================================

def generate_description(episode_title, episode_number=None):
    """Generate YouTube description from episode info."""
    desc = f"""Cat Podcast - {episode_title}

Simba and Meow are back with another episode! This time they talk about {episode_title.lower()}.

About the characters:
Simba - Confident, slightly stupid, works in Marketing, shares office gossip
Meow - Intelligent, sarcastic, works in Finance, keeps Simba in check

New episodes every week! Subscribe and hit the bell!

#CatPodcast #SimbaAndMeow #FunnyCats #OfficeHumor #Podcast"""

    if episode_number:
        desc += f"\n\nEpisode {episode_number} of The Simba Show"

    return desc


def generate_tags_from_title(title):
    """Generate tags from episode title."""
    base_tags = DEFAULT_TAGS.copy()

    # Add words from title
    words = title.lower().split()
    for word in words:
        if len(word) > 3 and word not in base_tags:
            base_tags.append(word)

    # Add common variations
    base_tags.extend([
        "the simba show",
        "cat talk",
        "office gossip",
        "workplace humor",
        "funny dialogue",
    ])

    return list(set(base_tags))[:50]  # Remove duplicates, max 50


# ============================================================
# MAIN FUNCTION
# ============================================================

def upload_episode(video_path, episode_title, episode_number=None, thumbnail_path=None, publish=True):
    """Upload a complete episode to YouTube."""
    # Generate metadata
    description = generate_description(episode_title, episode_number)
    tags = generate_tags_from_title(episode_title)

    privacy = "public" if publish else "private"

    result = upload_video(
        video_path=video_path,
        title=f"The Simba Show - {episode_title}",
        description=description,
        tags=tags,
        privacy_status=privacy,
        thumbnail_path=thumbnail_path,
    )

    # Save upload record
    if result:
        record_path = os.path.join(os.path.dirname(video_path), "upload_record.json")
        with open(record_path, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\nUpload record saved: {record_path}")

    return result


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python youtube_upload.py <video.mp4> <episode title> [thumbnail.png]")
        print("Example: python youtube_upload.py output/final.mp4 'Why Humans Work So Much' output/thumbnail.png")
        sys.exit(1)

    video = sys.argv[1]
    title = sys.argv[2]
    thumb = sys.argv[3] if len(sys.argv) > 3 else None

    upload_episode(video, title, thumbnail_path=thumb)