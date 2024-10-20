import re
import csv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import logging
from googleapiclient.discovery import build

# Necessary scopes for creating and modifying playlists
SCOPE = "playlist-modify-public user-read-private"

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def clean_metadata(text):
    """
    Clean metadata for titles, artists, and albums by removing irrelevant suffixes.
    """
    if text is None:
        return ""
    text = re.sub(r' - Topic$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\(.*?official.*?\)', '', text, flags=re.IGNORECASE)  # Remove "(official ...)"
    text = re.sub(r'\[.*?\]', '', text)  # Remove anything in brackets
    text = re.sub(r'\(.*?\)', '', text)  # Remove anything in parentheses
    text = re.sub(r'ft\.|feat\.|featuring', '', text, flags=re.IGNORECASE)  # Remove featuring mentions
    text = re.sub(r'(official|audio|video|music video|lyrics|HD|HQ)', '', text, flags=re.IGNORECASE)  # Remove other common terms
    return text.strip()

def search_spotify_track(sp, title, artist):
    """
    Search for a track on Spotify based on title and artist.
    """
    query = f"track:{title} artist:{artist}"
    logging.info(f"Searching for track: {title} by {artist} on Spotify.")
    results = sp.search(q=query, type='track', limit=1)

    if results['tracks']['items']:
        track_uri = results['tracks']['items'][0]['uri']
        logging.info(f"Found track URI: {track_uri}")
        return track_uri
    else:
        logging.warning(f"Track not found: {title} by {artist}")
        return None

def extract_playlist_info(youtube_api_key, playlist_id):
    """
    Extract song information from a YouTube playlist using the YouTube Data v3 API.
    """
    youtube = build('youtube', 'v3', developerKey=youtube_api_key)
    playlist_items = []
    next_page_token = None

    while True:
        request = youtube.playlistItems().list(
            part="snippet",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_page_token
        )
        response = request.execute()

        for item in response.get('items', []):
            if 'snippet' in item:
                snippet = item['snippet']
                title = snippet.get('title', 'Unknown Title')
                video_id = snippet['resourceId'].get('videoId', 'Unknown Video ID')
                artist = snippet.get('videoOwnerChannelTitle', 'Unknown Artist')
                
                playlist_items.append({
                    'title': title,
                    'video_id': video_id,
                    'artist': artist
                })

        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break

    return playlist_items

def create_spotify_client(client_id, client_secret):
    """
    Create a Spotify client with the given credentials and redirect URI.
    """
    redirect_uri = "https://tube2spotify.onrender.com/callback"
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=SCOPE
    ))

def export_playlist_to_csv(playlist_items, csv_filename):
    """
    Export playlist information to a CSV file.
    """
    if not playlist_items:
        logging.error("No playlist items to export.")
        return None

    with open(csv_filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=['Title', 'Artist', 'Album', 'Video ID', 'Duration'])
        writer.writeheader()
        for item in playlist_items:
            cleaned_title = clean_metadata(item['title'])
            cleaned_artist = clean_metadata(item['artist'])
            cleaned_album = clean_metadata(item.get('album', 'Unknown Album'))
            
            writer.writerow({
                'Title': cleaned_title,
                'Artist': cleaned_artist,
                'Album': cleaned_album,
                'Video ID': item['video_id'],
                'Duration': item.get('duration', '')
            })
    logging.info(f"Playlist exported to CSV: {csv_filename}")
    return csv_filename

def add_tracks_in_batches(sp, playlist_id, track_uris):
    """
    Add tracks to a Spotify playlist in batches to avoid exceeding API limits.
    """
    batch_size = 100
    for i in range(0, len(track_uris), batch_size):
        batch = track_uris[i:i + batch_size]
        sp.playlist_add_items(playlist_id, batch)
        logging.info(f"Added {len(batch)} tracks to the playlist.")

def transfer_to_spotify(sp, playlist_name, playlist_items):
    """
    Transfer playlist items to a new Spotify playlist.
    """
    logging.info("Starting playlist transfer to Spotify...")
    try:
        user_id = sp.me()['id']
        playlist = sp.user_playlist_create(user_id, playlist_name, public=False)
        logging.info(f"Playlist created with ID: {playlist['id']} and link: {playlist['external_urls']['spotify']}")

        track_uris = []
        for item in playlist_items:
            track_uri = search_spotify_track(sp, item['title'], item['artist'])
            if track_uri:
                track_uris.append(track_uri)

        if track_uris:
            add_tracks_in_batches(sp, playlist['id'], track_uris)
            logging.info(f"Playlist successfully updated with {len(track_uris)} tracks.")
        else:
            logging.warning("No tracks found to add to the playlist.")
    except Exception as e:
        logging.error(f"Failed to transfer playlist: {str(e)}")
        raise e

if __name__ == "__main__":
    # Code for testing the functions if needed
    pass
