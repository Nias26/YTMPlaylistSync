# DONE: Remove debug outputs (missing tracks, ...)
# DONE: Define types and document code
# DONE: Organize all in classes
# DONE: Save sensible data to config file (possibly `TOML` or `yaml` or the one that fits the best for python)
# DONE: Allow multiple playlist sync in different paths
# DONE: Use xdg environments of none provided from config
# DONE: Display program status for every function
# DONE: If file is already downoaded, update metadata
# DONE: Return specific type or none
# DONE: Implement exceptions
# DONE: Support editing of m3u files (check multiline comment)
# DONE: Create m3u if not exists
# TODO: Tidy help prompt
# TODO: Save tracks in database to save time and for better performance
# TODO: Display info for single tracks in db

from typing import Any
from yt_dlp import YoutubeDL
import os
import re
from mutagen.oggopus import OggOpus
from ytmusicapi import YTMusic
from halo import Halo
from pathlib import Path
import yaml

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader


class Track:
    title: str
    artist: list[str]
    album: str
    videoid: str

    def __init__(
        self,
        title: str,
        artist: list[str],
        album: str,
        videoid: str,
    ) -> None:
        self.title = title
        self.artist = artist
        self.album = album
        self.videoid = videoid

    def __getitem__(self, key: str) -> str:
        try:
            return getattr(self, key)
        except IndexError:
            raise KeyError(f"{key!r} is not a valid attribute")

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Track):
            return False

        return (
            other.title == self.title
            and other.artist == self.artist
            and other.album == self.album
            and other.videoid == self.videoid
        )

    def __hash__(self) -> int:
        return hash(
            (
                self.title,
                tuple(self.artist),
                self.album,
                self.videoid,
            )
        )


class MusicFile:
    path: Path
    filename: str
    metadata: Track

    def __init__(self, path: Path, filename: str, metadata: Track) -> None:
        self.path = path
        self.filename = filename
        self.metadata = metadata

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, MusicFile):
            return False
        return other.filename == self.filename and other.metadata == self.metadata

    def __hash__(self) -> int:
        return hash((self.path, self.filename, self.metadata))


class YTMPS:
    __ytmusic: YTMusic = YTMusic()
    __playlists_ids: list[str]
    __music_dir: Path
    __playlists_dirs: list[Path]
    __playlists_names: list[str]
    __m3u_filepath: Path

    def __init__(self, config: Path) -> None:
        stream = open(config, "r")
        data = yaml.load(stream, Loader=Loader)
        self.__music_dir = Path(data["music_dir"]).expanduser()
        self.__m3u_filepath = self.__music_dir / Path("Playlists")
        self.__playlists_dirs = [
            self.__music_dir / Path(playlist["name"]) for playlist in data["playlists"]
        ]
        self.__playlists_ids = [playlist["id"] for playlist in data["playlists"]]
        self.__playlists_names = [playlist["name"] for playlist in data["playlists"]]

        for playlist_dir in self.__playlists_dirs:
            if not playlist_dir.exists():
                playlist_dir.mkdir()

    def ytmusic_get_tracks(self) -> list[list[Track]]:
        entries: list[list[Track]] = []
        tracks: Any = []
        i: int = 0
        for playlist_id in self.__playlists_ids:
            entries.append([])
            tracks = self.__ytmusic.get_playlist(playlist_id, None).get("tracks")
            for track in tracks:
                entries[i].append(
                    Track(
                        track["title"],
                        (
                            [artists["name"] for artists in track["artists"]]
                            if track["artists"]
                            else [""]
                        ),
                        track["album"]["name"] if track["album"] else "",
                        track["videoId"],
                    )
                )
            i += 1
        return entries

    def read_local_tracks(self) -> list[list[MusicFile]]:
        tracks: list[list[MusicFile]] = []
        i: int = 0
        for playlist_dir in self.__playlists_dirs:
            tracks.append([])
            if os.path.exists(playlist_dir):
                with os.scandir(playlist_dir) as dir_entries:
                    for entry in dir_entries:
                        f = OggOpus(entry.path)
                        try:
                            tracks[i].append(
                                MusicFile(
                                    Path(entry.path),
                                    entry.name,
                                    Track(
                                        f["title"],
                                        f["artist"],
                                        f["album"],
                                        f["videoid"],
                                    ),
                                )
                            )
                        except Exception:
                            pass
            i += 1
        return tracks

    def get_to_update(self) -> list[list[Track]]:
        ids_to_download: list[list[Track]] = []

        local_tracks = self.read_local_tracks()
        online_tracks = self.ytmusic_get_tracks()
        for i in range(len(self.__playlists_ids)):
            ids_to_download.append([])
            local_tracks_id = {
                track.metadata["videoid"][0] for track in local_tracks[i]
            }
            # Check for video ids
            for online_track in online_tracks[i]:
                if online_track["videoid"] not in local_tracks_id:
                    ids_to_download[i].append(online_track)
            i += 1
        return ids_to_download

    def get_to_delete(self) -> list[list[MusicFile]]:
        files_to_delete: list[list[MusicFile]] = []

        online_tracks = self.ytmusic_get_tracks()
        local_tracks = self.read_local_tracks()
        for i in range(len(self.__playlists_ids)):
            files_to_delete.append([])
            online_tracks_id = {track["videoid"] for track in online_tracks[i]}
            # Check for video ids
            for local_track in local_tracks[i]:
                if local_track.metadata["videoid"][0] not in online_tracks_id:
                    # if no metadata found, then search videoid inside filename (fallback)
                    regex = re.compile(local_track.metadata["videoid"])
                    for track in local_tracks[i]:
                        if regex.search(track.filename):
                            files_to_delete[i].append(track)
            i += 1
        return files_to_delete

    def download_tracks(self, tracks: list[list[Track]]) -> list[list[Track]]:
        failed: list[list[Track]] = []

        i: int = 0
        for playlist in self.__playlists_dirs:
            failed.append([])
            opts: _Params = {
                "format": "bestaudio",
                "outtmpl": str(playlist) + "/" + "%(title)s [%(id)s].%(ext)s",
                "postprocessors": [{"key": "FFmpegExtractAudio"}],
                "quiet": True,
                "no_warnings": True,
            }

            for track in tracks[i]:
                spinner = Halo(
                    text="Downloading track " + track["title"], spinner="dots"
                )
                try:
                    with YoutubeDL(opts) as ydl:
                        spinner.start()
                        ydl.download(track["videoid"])
                except Exception:
                    failed[i].append(track)
                    spinner.fail("Failed to download track " + track["title"])

                spinner.succeed("Done")
            i += 1
        return failed

    def delete_tracks(self, music_files: list[list[MusicFile]]) -> None:
        spinner = Halo(text="Deleating old tracks", spinner="dots")
        spinner.start()
        for i in range(len(self.__playlists_ids)):
            for music_file in music_files[i]:
                os.remove(music_file.path)
            i += 1
        spinner.succeed("Done")

    def edit_metadatas(self, tracks: list[list[Track]]) -> None:
        spinner = Halo(text="Editing metadatas", spinner="dots")
        spinner.start()

        i: int = 0
        for playlist_dir in self.__playlists_dirs:
            for track in tracks[i]:
                regex_pattern = re.compile(track["videoid"])
                with os.scandir(playlist_dir) as dir_entries:
                    for entry in dir_entries:
                        if regex_pattern.search(entry.name):
                            f = OggOpus(entry.path)
                            f["title"] = track["title"]
                            f["artist"] = track["artist"]
                            f["album"] = track["album"]
                            f["videoid"] = track["videoid"]
                            f.save()
            i += 1
        spinner.succeed("Done")

    def edit_m3u_file(self, music_files: list[list[MusicFile]]) -> None:
        spinner = Halo(text="Editing m3u playlist", spinner="dots")
        spinner.start()
        i: int = 0
        for playlist_name in self.__playlists_names:
            with open(
                str(self.__m3u_filepath / Path(playlist_name)) + ".m3u", "w"
            ) as m3u_file:
                for music_file in music_files[i]:
                    path = Path(music_file.path)
                    m3u_file.write(f"{ Path(path.parts[-2]) / path.name}\n")
            i += 1
        spinner.succeed("Done")

    def sync(self, args):
        if args.option == "sync":
            tracks_to_update = self.get_to_update()
            failed: list[list[Track]] = self.download_tracks(tracks_to_update)
            self.edit_metadatas(tracks_to_update)

            for i in range(len(failed)):
                while len(failed[i]) > 0:
                    print("Trying to download again failed tracks...")
                    failed = self.download_tracks(failed)
                    self.edit_metadatas(failed)

            self.delete_tracks(self.get_to_delete())

            self.edit_m3u_file(self.read_local_tracks())

        if args.option == "debug":
            pass
