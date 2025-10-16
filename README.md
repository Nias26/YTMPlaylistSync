# YTMusic Playlist Sync

Tired of manually downloading songs and edit their metadatas every time you add something?
Tired of always creating a playlist on ncmpcpp for your messy mpd database?
Well... I introdue to you... YTMPlaylistSync!

It's a little project I made to sole this exact problem I **had**.

## Dependencies
`Python` >= 3.13
  - `argparse` >= 1.4.0
  - `pyxdg` >= 0.28
  - `yt-dlp` >= 2025.9.26
  - `mutagen` >= 1.47.0
  - `ytmusicapi` >= 1.11.1
  - `halo` >= 0.0.31
  -  `PyYAML` >= 6.0.3

## Installation
> [!NOTE]
> I still need to package it as a single file. For now clone the repository and symlink the executable
> to a folder in PATH (e.g. ~/.local/bin)

## Usage
Just run:
```
playlistmng sync
```
It will search for the file `config.yaml` inside your config directory

Syntax for config:
```yaml
music_dir: "~/Music"
playlists:
  - name: "Playlist"
    id: "<playlistId>"
  - name: "Breakcore"
    id: "<playlistId>"
  ...
```
