from flask import Flask, render_template, request, send_from_directory, redirect, url_for, flash
from googleapiclient.discovery import build
from export_playlist_github import extract_playlist_info, export_playlist_to_csv, clean_metadata, search_spotify_track, create_spotify_client, add_tracks_in_batches
import os
import json
import logging

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Changez cela pour une clé plus sécurisée

# S'assurer que le dossier static existe
if not os.path.exists('static'):
    os.makedirs('static')

# Configurer les logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Sauvegarder les données utilisateur
def save_user_data(data):
    with open('user_data.json', 'w') as file:
        json.dump(data, file)

# Charger les données utilisateur
def load_user_data():
    if os.path.exists('user_data.json'):
        with open('user_data.json', 'r') as file:
            return json.load(file)
    return {}  # Retourne un dictionnaire vide si aucun fichier n'existe

@app.route('/')
def index():
    user_data = load_user_data()  # Charge les données utilisateur depuis un fichier JSON, si elles existent
    return render_template('index.html', user_data=user_data)

@app.route('/export_csv', methods=['POST'])
def export_csv():
    # Récupérer les informations du formulaire
    youtube_api_key = request.form.get('youtube_api_key', '')
    playlist_id = request.form.get('playlist_id', '')

    # Enregistrer la clé API pour les futures utilisations
    save_user_data({
        'youtube_api_key': youtube_api_key,
        'spotify_client_id': '',
        'spotify_client_secret': ''
    })

    # Récupérer les éléments de la playlist YouTube
    playlist_items = extract_playlist_info(youtube_api_key, playlist_id)
    
    if not playlist_items:
        flash("Aucun élément trouvé dans la playlist.", "danger")
        return redirect(url_for('index'))

    # Nettoyer les métadonnées des éléments de la playlist
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

    # Nom du fichier CSV à générer
    csv_filename = 'exported_playlist.csv'
    csv_filepath = os.path.join('static', csv_filename)
    export_playlist_to_csv(cleaned_playlist_items, csv_filepath)

    flash("Playlist exportée avec succès. Vous pouvez la télécharger ci-dessous.", "success")
    return render_template('csv_result.html', csv_filename=csv_filename)

@app.route('/export_and_transfer', methods=['POST'])
def export_and_transfer():
    try:
        # Récupérer les informations nécessaires pour le transfert direct
        youtube_api_key = request.form.get('youtube_api_key', '')
        playlist_id = request.form.get('playlist_id', '')
        spotify_client_id = request.form.get('spotify_client_id', '')
        spotify_client_secret = request.form.get('spotify_client_secret', '')

        # Enregistrer les informations pour la prochaine fois
        save_user_data({
            'youtube_api_key': youtube_api_key,
            'spotify_client_id': spotify_client_id,
            'spotify_client_secret': spotify_client_secret
        })

        # Récupérer les éléments de la playlist YouTube
        playlist_items = extract_playlist_info(youtube_api_key, playlist_id)
        if not playlist_items:
            flash("Aucun élément trouvé dans la playlist.", "danger")
            return redirect(url_for('index'))

        # Nettoyer les métadonnées des éléments de la playlist
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

        # Créer le client Spotify et effectuer le transfert
        sp = create_spotify_client(spotify_client_id, spotify_client_secret, "http://localhost:8888/callback")
        user_id = sp.me()['id']
        playlist_name = "Transféré depuis YouTube"
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
            flash("Aucun morceau n'a été trouvé pour l'importation sur Spotify.", "warning")
            return redirect(url_for('index'))

    except Exception as e:
        logging.error(f"Erreur lors du transfert de la playlist vers Spotify : {str(e)}")
        flash(f"Erreur lors du transfert de la playlist vers Spotify : {str(e)}", "danger")
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
        flash("Le fichier demandé n'existe pas.", "danger")
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
