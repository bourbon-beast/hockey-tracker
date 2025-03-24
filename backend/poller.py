import firebase_admin
from firebase_admin import credentials, firestore
import requests
from bs4 import BeautifulSoup
import json
import logging
import time
import re
from datetime import datetime, timedelta
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"poller_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
BASE_URL = "https://www.revolutionise.com.au/vichockey/games/"
TEAM_FILTER = "Mentone"
TEAMS_FILE = "mentone_teams.json"
REQUEST_TIMEOUT = 10  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# Initialize Firebase
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate("path/to/serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")
        raise

db = firestore.client()

def make_request(url, retry_count=0):
    """
    Make an HTTP request with retries and error handling.

    Args:
        url (str): URL to request
        retry_count (int): Current retry attempt

    Returns:
        requests.Response or None: Response object if successful, None if failed
    """
    try:
        logger.debug(f"Requesting: {url}")
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        if retry_count < MAX_RETRIES:
            logger.warning(f"Request to {url} failed: {e}. Retrying ({retry_count+1}/{MAX_RETRIES})...")
            time.sleep(RETRY_DELAY)
            return make_request(url, retry_count + 1)
        else:
            logger.error(f"Request to {url} failed after {MAX_RETRIES} attempts: {e}")
            return None

def load_mentone_teams():
    """
    Load the Mentone teams from the JSON file.

    Returns:
        list: List of team dictionaries
    """
    try:
        with open(os.path.join("backend", TEAMS_FILE), "r") as f:
            teams = json.load(f)
        logger.info(f"Loaded {len(teams)} teams from {TEAMS_FILE}")
        return teams
    except Exception as e:
        logger.error(f"Failed to load teams from {TEAMS_FILE}: {e}")
        return []

def extract_game_details(game_element):
    """
    Extract game details from a game element in the HTML.

    Args:
        game_element (BeautifulSoup): Game element from the HTML

    Returns:
        dict: Game details
    """
    game_details = {}

    # Get date and time
    date_element = game_element.select_one(".fixture-details-date-long")
    if date_element:
        # Example: "Monday, 14 April 2025 - 7:30 PM"
        date_text = date_element.text.strip()
        try:
            date_parts = date_text.split(" - ")
            date_str = date_parts[0]  # "Monday, 14 April 2025"
            time_str = date_parts[1] if len(date_parts) > 1 else "12:00 PM"  # "7:30 PM"

            # Parse date and time
            datetime_str = f"{date_str} {time_str}"
            game_date = datetime.strptime(datetime_str, "%A, %d %B %Y %I:%M %p")
            game_details["date"] = game_date
        except Exception as e:
            logger.warning(f"Failed to parse date: {date_text}, error: {e}")
            game_details["date"] = None

    # Get venue
    venue_element = game_element.select_one(".fixture-details-venue")
    if venue_element:
        game_details["venue"] = venue_element.text.strip()

    # Get round
    round_element = game_element.select_one(".fixture-details-round")
    if round_element:
        round_text = round_element.text.strip()
        round_match = re.search(r"Round (\d+)", round_text)
        if round_match:
            game_details["round"] = int(round_match.group(1))

    # Get teams and scores
    teams_element = game_element.select_one(".fixture-details-teams")
    if teams_element:
        # Home team
        home_element = teams_element.select_one(".fixture-details-team-home")
        if home_element:
            home_name_element = home_element.select_one(".fixture-details-team-name")
            if home_name_element:
                game_details["home_team"] = {
                    "name": home_name_element.text.strip()
                }

            home_score_element = home_element.select_one(".fixture-details-team-score")
            if home_score_element:
                score_text = home_score_element.text.strip()
                if score_text and score_text != "-":
                    try:
                        game_details["home_team"]["score"] = int(score_text)
                    except ValueError:
                        logger.warning(f"Invalid home score: {score_text}")

        # Away team
        away_element = teams_element.select_one(".fixture-details-team-away")
        if away_element:
            away_name_element = away_element.select_one(".fixture-details-team-name")
            if away_name_element:
                game_details["away_team"] = {
                    "name": away_name_element.text.strip()
                }

            away_score_element = away_element.select_one(".fixture-details-team-score")
            if away_score_element:
                score_text = away_score_element.text.strip()
                if score_text and score_text != "-":
                    try:
                        game_details["away_team"]["score"] = int(score_text)
                    except ValueError:
                        logger.warning(f"Invalid away score: {score_text}")

    # Determine game status
    if "home_team" in game_details and "away_team" in game_details:
        home_score = game_details["home_team"].get("score")
        away_score = game_details["away_team"].get("score")

        if home_score is not None and away_score is not None:
            game_details["status"] = "completed"
        elif game_details.get("date") and game_details["date"] < datetime.now():
            game_details["status"] = "in_progress"
        else:
            game_details["status"] = "scheduled"

    return game_details

def fetch_team_games(team):
    """
    Fetch games for a specific team.

    Args:
        team (dict): Team dictionary

    Returns:
        list: List of game dictionaries
    """
    logger.info(f"Fetching games for team: {team['name']} (Fixture ID: {team['fixture_id']})")

    # Get team document from Firestore
    team_doc = db.collection("teams").document(f"team_{team['fixture_id']}").get()
    if not team_doc.exists:
        logger.warning(f"Team {team['name']} not found in Firestore")
        return []

    team_data = team_doc.to_dict()

    # Get competition document
    comp_doc = db.collection("competitions").document(f"comp_{team['comp_id']}").get()
    if not comp_doc.exists:
        logger.warning(f"Competition {team['comp_id']} not found in Firestore")
        comp_ref = None
    else:
        comp_ref = db.collection("competitions").document(f"comp_{team['comp_id']}")

    games = []

    # Fetch data for each round (up to 20 rounds)
    for round_num in range(1, 21):
        round_url = f"{BASE_URL}{team['comp_id']}/{team['fixture_id']}/round/{round_num}"
        response = make_request(round_url)

        if not response:
            # If we can't get this round, we've probably reached the end
            if round_num > 1:
                logger.debug(f"Reached end of rounds at round {round_num}")
                break
            else:
                logger.warning(f"Failed to fetch round 1 for team {team['name']}")
                continue

        soup = BeautifulSoup(response.text, "html.parser")

        # Find all games on this page
        game_elements = soup.select(".fixture-details")

        # Find games involving this team
        for game_element in game_elements:
            teams_element = game_element.select_one(".fixture-details-teams")
            if not teams_element:
                continue

            team_elements = teams_element.select(".fixture-details-team-name")
            team_names = [elem.text.strip() for elem in team_elements]

            # Check if this team is playing
            if any(team['name'] in name for name in team_names):
                # Extract game details
                game_details = extract_game_details(game_element)

                if game_details:
                    # Add team and competition references
                    game_details["team_ref"] = db.collection("teams").document(f"team_{team['fixture_id']}")
                    game_details["competition_ref"] = comp_ref

                    # Add team IDs to home and away teams
                    if "home_team" in game_details and team['name'] in game_details["home_team"]["name"]:
                        game_details["home_team"]["id"] = f"team_{team['fixture_id']}"

                    if "away_team" in game_details and team['name'] in game_details["away_team"]["name"]:
                        game_details["away_team"]["id"] = f"team_{team['fixture_id']}"

                    # Add fixture info
                    game_details["fixture_id"] = team['fixture_id']
                    game_details["comp_id"] = team['comp_id']

                    # Generate a unique ID for the game
                    game_id = f"game_{team['fixture_id']}_{round_num}_{hash(str(game_details)) % 1000}"
                    game_details["id"] = game_id

                    games.append(game_details)
                    logger.debug(f"Found game for {team['name']} in round {round_num}")

        # Short delay between round requests to be friendly to the server
        time.sleep(0.5)

    logger.info(f"Found {len(games)} games for team {team['name']}")