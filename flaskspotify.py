from flask import Flask, request, url_for, session, redirect, render_template
from spotipy import SpotifyOAuth
from urllib.parse import urlencode
import time
import requests
from flask_sqlalchemy import SQLAlchemy
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
db = SQLAlchemy(app)

class Tracks(db.Model):
    id = db.Column(db.String(200), primary_key=True)
    trackName = db.Column(db.String(200), nullable=False)
    artistName = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return f"Added Track: {self.trackName} by Artist: {self.artistName} with ID: {self.id}"

app.secret_key = "asdAS9434Dasd"
app.config['SESSION_COOKIE_NAME'] = "Berry's Cookie"
CLIENT_ID = "2e39d677bbd244dd995fa8bc2e0dbf90"
CLIENT_SECRET = "1c6dff1e656041579f9d04e25b458fb3"
TOKEN_INFO = "token_info"

def create_spotify_oauth():
    return SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=url_for('redirectPage', _external=True),
        scope="user-library-read,playlist-read-private,playlist-modify-public,playlist-modify-private",
        show_dialog=True
    )

def get_token():
    token_info = session.get(TOKEN_INFO, None)
    if not token_info:
        raise Exception("No token info")
    now = int(time.time())
    is_expired = token_info['expires_at'] - now < 60
    if is_expired:
        sp_oauth = create_spotify_oauth()
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
    return token_info

def get_access_token():
    try:
        token_info = get_token()
    except:
        print("User not logged in")
        return redirect(url_for('login'))
    access_token = token_info['access_token']
    return access_token

def searchSong(track, artist): # returns a dict holding trackName, artistName, and trackID
    access_token = get_access_token()
    endpoint = "https://api.spotify.com/v1/search"
    data = urlencode({"q": f"{track} {artist}", "type": "track"})
    lookup_url = f"{endpoint}?{data}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.get(lookup_url, headers=headers)
    response_json = response.json()
    results = response_json["tracks"]["items"]
    if results:
        artists = results[0]["artists"]
        artist_names = [artist["name"] for artist in artists]
        artist_names_string = ", ".join(artist_names)
        track_title = results[0]["name"]
        uri = results[0]["uri"]
        print(f"Top Result: {track_title} by {artist_names_string}. ID: {uri}")
        info = {
                "trackName" : track_title,
                "artistName" : artist_names_string,
                "trackID" : uri
                }
        return info
    else:
        raise Exception(f"No Track Found for artist {artist} and track {track}")

def getPlaylists():
    access_token = get_access_token()
    endpoint = "https://api.spotify.com/v1/me/playlists"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.get(endpoint, headers=headers)
    response_json = response.json()
    results = response_json["items"]
    playlists = {}
    if results:
        for playlist in results:
            playlists[playlist["name"]] = playlist["id"]
    return playlists

def addToPlayList(playlist_id, track_id):
    access_token = get_access_token()
    endpoint = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    data = {
        "uris": [track_id]
    }
    response = requests.post(endpoint, headers=headers, data=json.dumps(data))
    return response.status_code




@app.route('/')
def index():
    try:
        get_token()
    except:
        print("User not logged in")
        return redirect(url_for('login'))
    songs = Tracks.query.order_by(Tracks.trackName).all()
    return render_template('index.html', tracks=songs)

@app.route('/addSongs')
def addSongs():
    return render_template('addSongs.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/login')
def login():
    sp_oauth = create_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/redirect')
def redirectPage():
    sp_oauth = create_spotify_oauth()
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session[TOKEN_INFO] = token_info
    return redirect('/')

@app.route('/tracks', methods=['POST'])
def tracks():
    if request.method == 'POST': # Assumes first result is the one we want for now
        artist = request.form['artist']
        title = request.form['track']
        track_data = searchSong(title, artist)
        try:
            newTrack = Tracks(id=track_data["trackID"], trackName=track_data["trackName"], artistName=track_data["artistName"])
            db.session.add(newTrack)
            db.session.commit()
            print('added to db')
            return redirect(url_for('addSongs', _external=True))
        except:
            return 'There was an issue adding your track'

@app.route('/delete/<string:track_id>')
def delete(track_id):
    task_to_delete = Tracks.query.get_or_404(track_id)
    try:
        db.session.delete(task_to_delete)
        db.session.commit()
        return redirect("/")
    except:
        return "The was a problem deleting that task"

@app.route('/addToPlaylist/<string:track_id>', methods=['POST', 'GET'])
def addToPlaylist(track_id):
    if request.method == "POST":
        playlist_id = request.form['playlist']
        print(playlist_id)
        response = addToPlayList(playlist_id, track_id)
        print(response)
        if response == 201:
            print("ok")
            return redirect(f"/delete/{track_id}")
        return redirect('/')
    else:
        playlists = getPlaylists()
        return render_template('selectPlaylist.html', track_id=track_id, playlists=playlists)

app.run()
