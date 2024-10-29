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


def playlist_url_to_id(spotify_link: str):
    """Extracts the playlist ID from the URL"""
    if match := re.match(
        r"https://open\.spotify\.com/playlist/([a-zA-Z0-9]+)", spotify_link
    ):
        playlist_id = match.groups()[0]
        return playlist_id
    else:
        raise ValueError("Expected format: https://open.spotify.com/playlist/...")


# playlist_id = playlist_url_to_id(
#     "https://open.spotify.com/playlist/REPLACE-ME"
# )
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
    # Find all markdown links in the text
    links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", text)
    # Create a dictionary from the links
    return {display_text: url for display_text, url in links}


def extract_tags(text: str):
    """Extract tags from string"""
    # Match tags like `#foo`, `#bar-123`, etc.
    pattern = r"#\w[\w-]*"
    # Return matches as a list
    tags = re.findall(pattern, text)
    return tags


for dance_name, dance_df in dance_dataframes.items():
    dance_df["Links"] = dance_df["Links"].apply(markdown_to_dict)
    dance_df["Tags"] = dance_df["Tags"].apply(extract_tags)


def combine_dataframes_add_key_as_column(dance_dataframes):
    """Combine dataframes from dictionary into single one with extra column for the key"""
    df_list = []

    # Iterate over the dictionary and add the key as a new column
    for key, df in dance_dataframes.items():
        df["Dance"] = key
        df_list.append(df)

    # Concatenate all DataFrames in the list into a single DataFrame
    combined_df = pd.concat(df_list, ignore_index=True)

    return combined_df


dances_df = combine_dataframes_add_key_as_column(dance_dataframes)


# Find suggested dance name from notes based on artist and song name
def find_dance_via_name(song_name, artist_name, dances_df):
    """Try to match a song based oon artist and song name to a dance from the notes"""
    matching_rows = dances_df[
        (dances_df["Song"] == song_name) & (dances_df["Artist"] == artist_name)
    ]

    if not matching_rows.empty:
        # Return the 'source' column of the first matching row
        return matching_rows.iloc[0]["Dance"]
    return ""


def find_dance_via_link(dances_df, key, link):
    """Try to match a song based on the Spotify link to a dance from the notes"""
    for index, row in dances_df.iterrows():
        links_dict = row["Links"]
        # Check if Links is a dictionary and not empty
        if isinstance(links_dict, dict) and links_dict:
            # Check if the key exists and its value matches the link
            if key in links_dict and links_dict[key] == link:
                return row["Dance"]
    return ""


def find_dance_for_song(row, dances_df):

    # Get dance based on Spotify link
    result_from_link = find_dance_via_link(
        dances_df,
        "Spotify",
        row["spotify_url"],
    )

    # Get dance based on song name and artist name
    result_from_name = find_dance_via_name(row["Track Name"], row["Artists"], dances_df)

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
    lambda row: find_dance_for_song(row, dances_df),
    axis=1,
)


# Function to calculate start times
def calculate_start_times_aligned(df, start_time):
    """
    Calculate time at which each song starts playing based on playtime and initial start time,
    but only annotate times that align with 15-minute increments.
    Always print the first and last song times.
    """

    current_time = start_time
    start_times = []

    # Ensure the first 15-minute mark aligns to `:00`, `:15`, `:30`, `:45`
    next_15_min_mark = (
        current_time + timedelta(minutes=(15 - current_time.minute % 15))
    ).replace(second=0, microsecond=0)

    for index, row in df.iterrows():
        print(f"{index=}")
        if index == 14:  # Add extra time for a break, e.g. an announcement
            current_time += timedelta(milliseconds=5 * 60 * 1000)

        # Always print the first and last song's start time
        if index == 0 or index == len(df) - 1:
            start_times.append(current_time.strftime("%H:%M"))
        # Print times that align with 15-minute marks
        elif current_time >= next_15_min_mark:
            start_times.append(next_15_min_mark.strftime("%H:%M"))

            # Move to the next 15-minute mark
            next_15_min_mark += timedelta(minutes=15)
        else:
            start_times.append("")  # Leave blank if not on a 15-minute mark

        # Update current time based on song duration
        duration_ms = row["Duration (ms)"]
        current_time += timedelta(milliseconds=duration_ms)

    return start_times


# Calculate start times
playlist_df["Start Time"] = calculate_start_times_aligned(
    playlist_df, open_dancing_start_time
)

# # %%
# Save to CSV
playlist_df.to_csv(output_csv_name, index=True, index_label="index")
