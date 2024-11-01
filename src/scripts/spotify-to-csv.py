# %%
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import pandas as pd
import tomllib
import re
from markdown_it import MarkdownIt
from IPython.display import display
from datetime import datetime, timedelta
import networkx as nx
import matplotlib.pyplot as plt
from collections import defaultdict

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
break_time = datetime.strptime("21:00", "%H:%M")
break_duration = timedelta(minutes=10)

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
        df["Suggested Dance"] = key
        df_list.append(df)

    # Concatenate all DataFrames in the list into a single DataFrame
    combined_df = pd.concat(df_list, ignore_index=True)

    return combined_df


dances_df = combine_dataframes_add_key_as_column(dance_dataframes)


# Find suggested dance name from notes based on artist and song name
def match_on_name(songs_row, dances_row) -> bool:
    """Try to match a song based on artist and song name to a dance from the notes"""
    return (
        songs_row["Track Name"] == dances_row["Song"]
        and songs_row["Artists"] == dances_row["Artist"]
    )


def match_on_link(songs_row, dances_row) -> bool:
    """Try to match a song based on the Spotify link to a dance from the notes"""
    links_dict = dances_row["Links"]
    # Check if Links is a dictionary and not empty
    if isinstance(links_dict, dict) and links_dict:
        # Check if the key exists and its value matches the link
        key = "Spotify"
        link = songs_row["spotify_url"]
        if key in links_dict and links_dict[key] == link:
            return True
    return False


def match_on_song(songs_row, dances_row) -> bool:

    # Get dance based on Spotify link
    link_result = match_on_link(songs_row, dances_row)
    # Get dance based on song name and artist name
    name_result = match_on_name(songs_row, dances_row)

    # Throw error if no link and only name
    if name_result and not link_result:
        print(f"{songs_row["Track Name"]=}")
        print(f"{songs_row["Artists"]=}")
        print(f"{dances_row["Links"]=}")
        assert name_result
        assert link_result

    # Return if either matched
    return link_result or name_result


def slow_join_check_links(playlist_df, dances_df):
    # TODO: drops rows from playlist dataframe if not in dances notes
    # Join dataframes on the dance using custom matching function and only keep relevant columns
    cross_joined_df = playlist_df.merge(dances_df, how="cross")
    matched_df = cross_joined_df[
        cross_joined_df.apply(
            lambda row: match_on_song(
                row[["spotify_url", "Track Name", "Artists"]],
                row[["Song", "Artist", "Links"]],
            ),
            axis=1,
        )
    ]
    combined_filtered_df = matched_df[
        [
            "Track Name",
            "Artists",
            "Duration (ms)",
            "Duration (min:sec)",
            "id",
            "spotify_url",
            "BPM",
            "Notes",
            "Tags",
            "Count",
            "Suggested Dance",
            "Links",
        ]
    ]
    # Reset index
    combined_filtered_df = combined_filtered_df.reset_index(drop=True)
    return combined_filtered_df


def fast_join_links_only(playlist_df, dances_df):
    # Extract Spotify URL as key for more efficient merging
    dances_df["spotify_url"] = dances_df["Links"].apply(lambda x: x.get("Spotify"))

    # Filter potential matches based on these keys to reduce cross-join size
    initial_match_df = playlist_df.merge(
        dances_df,
        how='left',
        on="spotify_url",
    )

    # Vectorize Spotify link matching
    initial_match_df["link_match"] = initial_match_df.apply(
        lambda row: row["spotify_url"] == row["spotify_url"],
        axis=1,
    )
    # Filter where links match
    final_matched_df = initial_match_df[initial_match_df["link_match"]]

    # Select and rename columns as required
    combined_filtered_df = final_matched_df[
        [
            "Track Name",
            "Artists",
            "Duration (ms)",
            "Duration (min:sec)",
            "id",
            "spotify_url",
            "BPM",
            "Notes",
            "Tags",
            "Count",
            "Suggested Dance",
            "Links",
        ]
    ]
    # Reset index
    combined_filtered_df = combined_filtered_df.reset_index(drop=True)
    return combined_filtered_df


combined_filtered_df = slow_join_check_links(playlist_df, dances_df)
combined_filtered_df = fast_join_links_only(playlist_df, dances_df)


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

    added_break = False
    for index, row in df.iterrows():
        if (
            not added_break and current_time >= break_time
        ):  # Add extra time for a break, e.g. an announcement
            current_time += break_duration
            added_break = True

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
combined_filtered_df["Start Time"] = calculate_start_times_aligned(
    combined_filtered_df, open_dancing_start_time
)

# %%


class DanceStateMachine:
    """
    A state machine and logic to check whether the songs and the corresponding dances fulfill the suggested order
    https://wiki.tanzquotient.org/open-dancing#OpenDancing-OpenDancing
    """

    def __init__(self):
        self.graph = defaultdict(list)
        self.dance_counts = defaultdict(int)
        self.errors = []
        self.block_count = 0
        self.order_results = []

        # Define the state transitions
        self.add_transition(
            "Salsa",
            "Bachata",
            "English Waltz",
            "English Tango",
            "Viennese Waltz",
            "Slow Fox",
            "Quickstep",
            "Discofox",
            "Lindy Hop",
            "Charleston",
            "Samba",
            "Cha Cha Cha",
            "Rumba",
            "Paso Doble",
            "Jive",
            "Tango Argentino",
            "Kizomba / Zouk",
            "Polka",
            "Choreo",
        )
        self.add_transition(
            "Salsa",
            "Bachata",
        )
        self.add_transition(
            "Bachata",
            "English Waltz",
        )
        self.add_transition(
            "English Waltz",
            "English Tango",
        )
        self.add_transition(
            "English Tango",
            "Viennese Waltz",
        )
        self.add_transition(
            "Viennese Waltz",
            "Slow Fox",
            "Quickstep",
        )
        self.add_transition(
            "Slow Fox",
            "Quickstep",
        )
        self.add_transition(
            "Quickstep",
            "Discofox",
        )
        self.add_transition(
            "Discofox",
            "Lindy Hop",
            "Charleston",
            "Samba",
            "Cha Cha Cha",
        )
        self.add_transition(
            "Lindy Hop",
            "Samba",
            "Cha Cha Cha",
        )
        self.add_transition(
            "Charleston",
            "Samba",
            "Cha Cha Cha",
        )
        self.add_transition(
            "Samba",
            "Cha Cha Cha",
        )
        self.add_transition(
            "Cha Cha Cha",
            "Rumba",
        )
        self.add_transition(
            "Rumba",
            "Paso Doble",
            "Jive",
        )
        self.add_transition(
            "Paso Doble",
            "Jive",
        )
        self.add_transition(
            "Jive",
            "Tango Argentino",
            "Kizomba / Zouk",
            "Polka",
            "Salsa",
            "Choreo",
        )
        self.add_transition(
            "Tango Argentino",
            "Kizomba / Zouk",
            "Polka",
            "Salsa",
            "Choreo",
        )
        self.add_transition(
            "Kizomba / Zouk",
            "Polka",
            "Salsa",
        )
        self.add_transition(
            "Polka",
            "Salsa",
        )
        self.add_transition(
            "Choreo",
            "Salsa",
        )

        # Define special rules
        self.special_rules = {
            "Slow Fox": {"frequency": "every_other", "max_count": None},
            "Samba": {"frequency": "every_other", "max_count": None},
            "Paso Doble": {"frequency": "every_other", "max_count": None},
            "Lindy Hop": {"frequency": "at_least_once", "min_count": 1},
            "Charleston": {"frequency": "once", "max_count": 1},
            "Tango Argentino": {
                "frequency": "few_times",
                "min_count": 1,
                "max_count": 5,
            },
            "Kizomba / Zouk": {"frequency": "maybe_once", "max_count": 1},
            "Polka": {"frequency": "maybe_once_or_twice", "max_count": 2},
        }

    def add_transition(self, from_state, *to_states):
        self.graph[from_state].extend(to_states)

    def check_order(self, dances):
        current_state = dances[0]
        self.dance_counts[current_state] += 1
        self.order_results.append(True)  # First dance has no transition to check

        for i, dance in enumerate(dances[1:], 1):
            if dance in self.graph[current_state]:
                self.order_results.append(True)
            else:
                self.errors.append(
                    f"Invalid transition from {current_state} to {dance} at position {i+1}"
                )
                self.order_results.append(False)
            self.dance_counts[dance] += 1
            if dance == "Salsa":
                self.block_count += 1
            current_state = dance

    def check_special_rules(self):
        for dance, rule in self.special_rules.items():
            count = self.dance_counts[dance]
            if rule["frequency"] == "every_other":
                if count > (self.block_count + 1) // 2:
                    self.errors.append(
                        f"{dance} appeared too frequently ({count} times in {self.block_count} blocks)"
                    )
                if count < (self.block_count - 1) // 2:
                    self.errors.append(
                        f"{dance} appeared too rarely ({count} times in {self.block_count} blocks)"
                    )
            elif "min_count" in rule and count < rule["min_count"]:
                self.errors.append(f"{dance} appeared too few times ({count})")
            elif "max_count" in rule and count > rule["max_count"]:
                self.errors.append(f"{dance} appeared too many times ({count})")

    def print_results(self):
        if self.errors:
            print("The following errors were found:")
            for error in self.errors:
                print(f"- {error}")
        else:
            print("All requirements are met!")

        print("\nDance counts:")
        for dance, count in self.dance_counts.items():
            print(f"{dance}: {count}")

    def visualize_graph(self):
        G = nx.DiGraph()
        for from_state, to_states in self.graph.items():
            for to_state in to_states:
                G.add_edge(from_state, to_state)

        pos = nx.shell_layout(G)
        plt.figure(figsize=(20, 12))
        nx.draw(
            G,
            pos,
            with_labels=True,
            node_color="lightblue",
            node_size=3000,
            font_size=10,
            font_weight="bold",
            arrows=True,
            arrowsize=20,
        )

        # Add labels to edges
        edge_labels = {(u, v): "" for (u, v) in G.edges()}
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=8)

        # Adjust node labels
        nx.draw_networkx_labels(
            G,
            pos,
            {
                node: f'{node}\n{self.special_rules.get(node, {}).get("frequency", "")}'
                for node in G.nodes()
            },
            font_size=8,
        )

        plt.title("Dance Transition Graph", fontsize=20)
        plt.axis("off")
        plt.tight_layout()
        plt.show()


def check_dance_order(df):
    dances = df["Suggested Dance"].tolist()
    state_machine = DanceStateMachine()
    state_machine.check_order(dances)
    state_machine.check_special_rules()
    state_machine.print_results()
    state_machine.visualize_graph()

    # Create new dataframe with results
    new_df = df.copy()
    new_df["Is Correct Order"] = state_machine.order_results
    return new_df


# Check dance order and get new dataframe with checked results
checked_df = check_dance_order(combined_filtered_df)

# # %%
# Save to CSV
checked_df.to_csv(output_csv_name, index=True, index_label="index")
