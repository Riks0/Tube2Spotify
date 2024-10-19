import re
import csv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import logging

# Scopes required to create and modify playlists
SCOPE = "playlist-modify-public user-read-private"

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def clean_metadata(text):
    """
    Clean the metadata of titles and artists by removing irrelevant suffixes.
    """
    # Remove "- Topic" and other irrelevant keywords
    text = re.sub(r' - Topic$', '', text)  # Remove the " - Topic" suffix
    text = re.sub(r'\(.*?\)', '', text)  # Remove anything within parentheses (like Official Music Video)
    return text.strip()

def read_playlist_csv(filename):
    playlist = []
    with open(filename, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            cleaned_title = clean_metadata(row['Title'])
            cleaned_artist = clean_metadata(row['Artist'])
            playlist.append({
                'Title': cleaned_title,
                'Artist': cleaned_artist
            })
    return playlist

def create_spotify_client(client_id, client_secret, redirect_uri):
    """
    Creates an authenticated Spotify client with the provided credentials.
    """
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=SCOPE
    ))

def search_spotify_track(sp, title, artist):
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

def add_tracks_in_batches(sp, playlist_id, track_uris):
    batch_size = 100
    for i in range(0, len(track_uris), batch_size):
        batch = track_uris[i:i + batch_size]
        sp.playlist_add_items(playlist_id, batch)
        logging.info(f"Added {len(batch)} tracks to the playlist.")

def import_playlist_from_csv(csv_filename, client_id, client_secret, redirect_uri):
    """
    Imports a playlist from a CSV file to Spotify.
    """
    sp = create_spotify_client(client_id, client_secret, redirect_uri)

    playlist_data = read_playlist_csv(csv_filename)

    user_id = sp.me()['id']
    playlist_name = "My CSV Playlist"
    playlist = sp.user_playlist_create(user_id, playlist_name, public=True)
    logging.info(f"Created Spotify playlist: {playlist['external_urls']['spotify']}")

    track_uris = []
    for track in playlist_data:
        title = track['Title']
        artist = track['Artist']
        track_uri = search_spotify_track(sp, title, artist)
        if track_uri:
            track_uris.append(track_uri)

    if track_uris:
        add_tracks_in_batches(sp, playlist['id'], track_uris)
        logging.info(f"Playlist successfully updated with {len(track_uris)} tracks.")
    else:
        logging.warning("No tracks were added to the playlist.")
