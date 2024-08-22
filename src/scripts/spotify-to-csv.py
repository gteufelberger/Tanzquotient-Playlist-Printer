# %%
from tokenize import String
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import pandas as pd
import tomllib
import re
from markdown_it import MarkdownIt
from IPython.display import display
from datetime import datetime, timedelta

# Load credentials
with open("credentials.toml", "rb") as f:
    credentials = tomllib.load(f)

# Authenticate
sp = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=credentials["spotify"]["client_id"],
        client_secret=credentials["spotify"]["client_secret"],
    )
)

playlist_id = "REPLACE-ME"
output_csv_name = "open-dancing-playlist.csv"
markdown_notes_filename = "notes.md"
# Start time of Open Dancing / the playlist
open_dancing_start_time = datetime.strptime("20:20", "%H:%M")

# Get playlist details
results = sp.playlist_tracks(playlist_id)


# Parse playlist into dataframe


def ms_to_min_sec(milliseconds):
    """Helper function to print milliseconds as `M:SS`"""
    seconds = (milliseconds // 1000) % 60
    minutes = (milliseconds // (1000 * 60)) % 60
    return f"{minutes}:{seconds:02d}"


def get_playlist_tracks(playlist_id):
    """Fetches all tracks from a Spotify playlist and stores them in a list"""
    results = sp.playlist_tracks(playlist_id)
    tracks = results["items"]

    # Continue fetching tracks until we get all of them
    while results["next"]:
        results = sp.next(results)
        tracks.extend(results["items"])

    return tracks


def create_playlist_dataframe(playlist_id):
    """Takes a Spotify playlist id and converts the playlist into a pandas dataframe"""
    tracks = get_playlist_tracks(playlist_id)

    track_list = []
    for item in tracks:
        track = item["track"]
        track_name = track["name"]
        artist_names = ", ".join([artist["name"] for artist in track["artists"]])
        id = track["id"]
        spotify_url = track["external_urls"]["spotify"]
        duration_ms = track["duration_ms"]
        duration_min_sec = ms_to_min_sec(duration_ms)
        track_list.append(
            {
                "Track Name": track_name,
                "Artists": artist_names,
                "Duration (ms)": duration_ms,
                "Duration (min:sec)": duration_min_sec,
                "id": id,
                "spotify_url": spotify_url,
            }
        )

    df = pd.DataFrame(track_list)
    return df


playlist_df = create_playlist_dataframe(playlist_id)


# %%
# Parse markdown notes


def parse_table(tokens):
    """Custom markdown table parser cause I couldn't find a working existing one"""
    rows = []
    headers = []
    current_row = []

    for token in tokens:
        if token.type == "tr_open":
            current_row = []
        elif token.type == "tr_close":
            if headers:
                rows.append(current_row)
            else:
                headers = current_row
        elif token.type == "td_open" or token.type == "th_open":
            cell_content = next(tokens)
            current_row.append(cell_content.content.strip())

    return headers, rows


def extract_tables_with_headers(markdown_content):
    """Takes a string containing a markdown document and returns a dictionary of tables"""
    md = MarkdownIt().enable("table")
    tokens = md.parse(markdown_content)
    tables = {}
    inside_table = False
    table_tokens = []
    current_header = None
    tokens_iter = iter(tokens)

    for token in tokens_iter:
        if token.type == "heading_open" and token.tag == "h3":
            current_header = next(tokens_iter).content.strip()
        elif token.type == "table_open":
            inside_table = True
            table_tokens = []
        elif token.type == "table_close":
            inside_table = False
            headers, rows = parse_table(iter(table_tokens))
            table = pd.DataFrame(rows, columns=headers)
            if current_header:
                tables[current_header] = table
                current_header = None
        if inside_table:
            table_tokens.append(token)

    return tables


# Read the Markdown file
with open(markdown_notes_filename, "r") as file:
    markdown_content = file.read()


dance_dataframes = extract_tables_with_headers(markdown_content)


def markdown_to_dict(text):
    """Converts Markdown links to dictionary with display text being the key and the URL being the value"""
    print(f"{text=}")
    # Find all markdown links in the text
    links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", text)
    # Create a dictionary from the links
    return {display: url for display, url in links}


for dance_name, dance_df in dance_dataframes.items():
    dance_df["Links"] = dance_df["Links"].apply(markdown_to_dict)


# Find suggested dance name from notes based on artist and song name
def find_dance_via_name(song_name, artist_name, dance_dataframes):
    """Try to match a song based oon artist and song name to a dance from the notes"""
    for dance_name, df in dance_dataframes.items():
        if ((df["Song"] == song_name) & (df["Artist"] == artist_name)).any():
            return dance_name
    return ""


def find_dance_via_link(df, key, link):
    """Try to match a song based on the Spotify link to a dance from the notes"""
    for dance_name, df in dance_dataframes.items():
        for index, row in df.iterrows():
            links_dict = row["Links"]
            # Check if Links is a dictionary and not empty
            if isinstance(links_dict, dict) and links_dict:
                # Check if the key exists and its value matches the link
                if key in links_dict and links_dict[key] == link:
                    return dance_name
    return ""


def find_dance_for_song(row):

    # Get dance based on Spotify link
    result_from_link = find_dance_via_link(
        dance_dataframes,
        "Spotify",
        row["spotify_url"],
    )

    # Get dance based on song name and artist name
    result_from_name = find_dance_via_name(
        row["Track Name"], row["Artists"], dance_dataframes
    )

    # Make sure that the two match if both were found
    if result_from_name != "" and result_from_link != "":
        assert (
            result_from_name == result_from_link
        ), f"Mismatch {result_from_name=}{result_from_link=}"

    if result_from_name != "":
        return result_from_name

    if result_from_link != "":
        return result_from_link
    return ""


# Add a new column for the dance name
playlist_df["Suggested Dance"] = playlist_df.apply(
    lambda row: find_dance_for_song(row),
    axis=1,
)


# Function to calculate start times
def calculate_start_times(df, start_time):
    """Calculate time at which each song starts playing based on playtime and initial start time"""
    current_time = start_time
    start_times = []

    for index, row in df.iterrows():
        print(f"{index=}")
        if index == 14:
            current_time += timedelta(milliseconds=5 * 60 * 1000)

        start_times.append(current_time.strftime("%H:%M"))
        duration_ms = row["Duration (ms)"]
        current_time += timedelta(milliseconds=duration_ms)

    return start_times


# Calculate start times
playlist_df["Start Time"] = calculate_start_times(playlist_df, open_dancing_start_time)

# # %%
# Save to CSV
playlist_df.to_csv(output_csv_name, index=True, index_label="index")
