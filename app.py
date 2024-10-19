from flask import Flask, render_template, request, send_from_directory, redirect, url_for, flash
from googleapiclient.discovery import build
from export_playlist_github import extract_playlist_info, export_playlist_to_csv, clean_metadata, search_spotify_track, create_spotify_client, add_tracks_in_batches
import os
import json
import logging

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a more secure key

# Ensure that the static folder exists
if not os.path.exists('static'):
    os.makedirs('static')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Save user data
def save_user_data(data):
    with open('user_data.json', 'w') as file:
        json.dump(data, file)

# Load user data
def load_user_data():
    if os.path.exists('user_data.json'):
        with open('user_data.json', 'r') as file:
            return json.load(file)
    return {}  # Returns an empty dictionary if no file exists

@app.route('/')
def index():
    user_data = load_user_data()  # Load user data from a JSON file, if available
    return render_template('index.html', user_data=user_data)

@app.route('/export_csv', methods=['POST'])
def export_csv():
    # Retrieve information from the form
    youtube_api_key = request.form.get('youtube_api_key', '')
    playlist_id = request.form.get('playlist_id', '')

    # Save the API key for future use
    save_user_data({
        'youtube_api_key': youtube_api_key,
        'spotify_client_id': '',
        'spotify_client_secret': ''
    })

    # Retrieve the items of the YouTube playlist
    playlist_items = extract_playlist_info(youtube_api_key, playlist_id)
    
    if not playlist_items:
        flash("No items found in the playlist.", "danger")
        return redirect(url_for('index'))

    # Clean the metadata of the playlist items
    cleaned_playlist_items = [
        {
            'title': clean_metadata(item['title']),
            'artist': clean_metadata(item['artist']),
            'album': clean_metadata(item.get('album', '')),
            'video_id': item['video_id'],
            'duration': item.get('duration', '')
        }
        for item in playlist_items
    ]

    # Name of the CSV file to generate
    csv_filename = 'exported_playlist.csv'
    csv_filepath = os.path.join('static', csv_filename)
    export_playlist_to_csv(cleaned_playlist_items, csv_filepath)

    flash("Playlist successfully exported. You can download it below.", "success")
    return render_template('csv_result.html', csv_filename=csv_filename)

@app.route('/export_and_transfer', methods=['POST'])
def export_and_transfer():
    try:
        # Retrieve the necessary information for direct transfer
        youtube_api_key = request.form.get('youtube_api_key', '')
        playlist_id = request.form.get('playlist_id', '')
        spotify_client_id = request.form.get('spotify_client_id', '')
        spotify_client_secret = request.form.get('spotify_client_secret', '')

        # Save the information for next time
        save_user_data({
            'youtube_api_key': youtube_api_key,
            'spotify_client_id': spotify_client_id,
            'spotify_client_secret': spotify_client_secret
        })

        # Retrieve the items of the YouTube playlist
        playlist_items = extract_playlist_info(youtube_api_key, playlist_id)
        if not playlist_items:
            flash("No items found in the playlist.", "danger")
            return redirect(url_for('index'))

        # Clean the metadata of the playlist items
        cleaned_playlist_items = [
            {
                'title': clean_metadata(item['title']),
                'artist': clean_metadata(item['artist']),
                'album': clean_metadata(item.get('album', '')),
                'video_id': item['video_id'],
                'duration': item.get('duration', '')
            }
            for item in playlist_items
        ]

        # Create the Spotify client and perform the transfer
        sp = create_spotify_client(spotify_client_id, spotify_client_secret, "http://localhost:8888/callback")
        user_id = sp.me()['id']
        playlist_name = "Transferred from YouTube"
        playlist = sp.user_playlist_create(user_id, playlist_name, public=True)
        spotify_playlist_url = playlist['external_urls']['spotify']

        track_uris = []
        for item in cleaned_playlist_items:
            track_uri = search_spotify_track(sp, item['title'], item['artist'])
            if track_uri:
                track_uris.append(track_uri)

        if track_uris:
            add_tracks_in_batches(sp, playlist['id'], track_uris)
            return render_template('success.html', spotify_playlist_url=spotify_playlist_url)
        else:
            flash("No tracks found for import to Spotify.", "warning")
            return redirect(url_for('index'))

    except Exception as e:
        logging.error(f"Error during playlist transfer to Spotify: {str(e)}")
        flash(f"Error during playlist transfer to Spotify: {str(e)}", "danger")
        return redirect(url_for('index'))

@app.route('/success')
def success():
    spotify_playlist_url = request.args.get('spotify_playlist_url', None)
    return render_template('success.html', spotify_playlist_url=spotify_playlist_url)

@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_from_directory('static', filename, as_attachment=True)
    except FileNotFoundError:
        flash("The requested file does not exist.", "danger")
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
