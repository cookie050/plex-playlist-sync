import logging
import sys
from typing import List

import deezer
import spotipy
from plexapi.exceptions import BadRequest, NotFound
from plexapi.server import PlexServer

logging.basicConfig(stream=sys.stdout, level=logging.INFO)


def get_sp_user_playlists(sp: spotipy.Spotify, userId: str):
    """Gets all the playlist URIs for the given userId

    Args:
        sp (spotipy.Spotify): Spotify configured instance
        userId (str): UserId of the spotify account (get it from open.spotify.com/account)

    Returns:
        list[str]: list of URIs
    """
    playlists = sp.user_playlists(userId)
    return ([(playlist['uri'], playlist['name']) for playlist in playlists['items']])


def get_sp_playlist_tracks(sp, userId: str, playlistId: str) -> List:
    """Gets tracks in a given playlist

    Args:
        sp ([type]): Spotify configured instance
        userId (str): UserId of the spotify account (get it from open.spotify.com/account)
        playlistId (str): Playlist URI

    Returns:
        List: A list of track objects
    """
    results = sp.user_playlist_tracks(userId, playlistId)
    tracks = results['items']
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])
    return tracks


def get_sp_track_names(sp, userId: str, playlistId: str) -> List:
    """Returns the track names, artists of the given spotify playlist

    Args:
        sp ([type]): Spotify configured instance
        userId (str): UserId of the spotify account
        playlistId (str): Playlist URI

    Returns:
        zip(list, list): A zip object of track name and corresponding artist
    """
    trackNames, artistNames = [], []
    tracks = get_sp_playlist_tracks(sp, userId, playlistId)
    for track in tracks:
        trackNames.append(track['track']['name'])
        artistNames.append(track['track']['artists'][0]['name'])
    return zip(trackNames, artistNames)


def get_deez_playlist_track_names(deezer: deezer.Client(), playlistId: str) -> List:
    """Returns the track names, artists of the given deezer playlist Id

    Args:
        deezer (deezer.Client): Deezer Client (no credentials needed)
        playlistId (str): Playlist ID

    Returns:
        zip(list, list): A zip object of track name and corresponding artist
    """
    trackNames, artistNames = [], []
    tracks = deezer.get_playlist(playlistId).tracks
    for track in tracks:
        trackNames.append(track.title)
        artistNames.append(track.artist.name)

    return zip(trackNames, artistNames)


def get_available_plex_tracks(plex: PlexServer, trackZip: List) -> List:
    """For the given spotify track names returns a list of plex.audio.track objects
        - Empty list if none of the tracks are found in Plex

    Args:
        plex (PlexServer): A configured PlexServer instance
        trackNames (List): List of track names

    Returns:
        List: of track objects
    """
    musicTracks = []
    for track, artist in trackZip:
        try:
            search = plex.search(track, mediatype='track', limit=5)
        except BadRequest:
            logging.info("failed to search %s" % track)
            search = []
        if not search:
            search = plex.search(
                track.split('(')[0], mediatype='track', limit=5
            )
        if search:
            for s in search:
                try:
                    if s.artist().title.lower() == artist.lower():
                        musicTracks.extend(s)
                        break

                except IndexError:
                    logging.info(
                        "Looks like plex mismatched the search for %s, retrying with next query" % track)
    return musicTracks


def create_new_plex_playlist(plex: PlexServer, tracksList: List, playlistName: str) -> None:
    """Creates a new plex playlist with given name and tracks

    Args:
        plex (PlexServer): A configured PlexServer instance
        tracksList (List): List of plex.audio.track objects
        playlistName (str): Name of the playlist
    """
    plex.createPlaylist(title=playlistName, items=tracksList)


def create_plex_playlist(plex: PlexServer, tracksList: List, playlistName: str) -> None:
    """Deletes existing playlist (if exists) and creates a new playlist with given name and playlist name

    Args:
        plex (PlexServer): A configured PlexServer instance
        tracksList (List):List of plex.audio.track objects
        playlistName (str): Name of the playlist
    """
    try:
        plexPlaylist = plex.playlist(playlistName)
        plexPlaylist.delete()
        logging.info("Deleted existing playlist %s" % playlistName)
        create_new_plex_playlist(plex, tracksList, playlistName)
        logging.info("Created playlist %s" % playlistName)

    except NotFound:
        create_new_plex_playlist(plex, tracksList, playlistName)
        logging.info("Created playlist %s" % playlistName)
