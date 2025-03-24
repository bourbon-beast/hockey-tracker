import firebase_admin
from firebase_admin import credentials, firestore
import requests
from bs4 import BeautifulSoup
import json
import logging
import time
import os
from datetime import datetime

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"poller_init_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Config ---
BASE_URL = "https://www.revolutionise.com.au/vichockey/games/"
TEAMS_FILE = os.path.join("backend", "mentone_teams.json")
REQUEST_TIMEOUT = 10
MAX_RETRIES = 3
RETRY_DELAY = 2

# --- Firebase ---
if not firebase_admin._apps:
    cred = credentials.Certificate("path/to/serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

# --- Helpers ---
def make_request(url, retry_count=0):
    try:
        logger.debug(f"Requesting: {url}")
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        if retry_count < MAX_RETRIES:
            logger.warning(f"Retrying {url}: {e}")
            time.sleep(RETRY_DELAY)
            return make_request(url, retry_count + 1)
        else:
            logger.error(f"Failed to fetch {url} after retries: {e}")
            return None

def load_mentone_teams():
    try:
        with open(TEAMS_FILE, "r") as f:
            teams = json.load(f)
        return teams
    except Exception as e:
        logger.error(f"Failed to load teams: {e}")
        return []

def extract_game_details(game_element):
    game = {}

    # Date and time
    dt_el = game_element.select_one(".fixture-details-date-long")
    if dt_el:
        date_text = dt_el.text.strip()
        try:
            parts = date_text.split(" - ")
            date_str = parts[0]
            time_str = parts[1] if len(parts) > 1 else "12:00 PM"
            dt = datetime.strptime(f"{date_str} {time_str}", "%A, %d %B %Y %I:%M %p")
            game["date"] = dt
        except:
            game["date"] = None

    venue_el = game_element.select_one(".fixture-details-venue")
    if venue_el:
        game["venue"] = venue_el.text.strip()

    round_el = game_element.select_one(".fixture-details-round")
    if round_el:
        match = re.search(r"Round (\d+)", round_el.text)
        if match:
            game["round"] = int(match.group(1))

    teams_el = game_element.select_one(".fixture-details-teams")
    if teams_el:
        home_el = teams_el.select_one(".fixture-details-team-home")
        away_el = teams_el.select_one(".fixture-details-team-away")
        if home_el:
            name_el = home_el.select_one(".fixture-details-team-name")
            game["home_team"] = {"name": name_el.text.strip()} if name_el else {}
        if away_el:
            name_el = away_el.select_one(".fixture-details-team-name")
            game["away_team"] = {"name": name_el.text.strip()} if name_el else {}

    game["status"] = "scheduled"
    return game

def fetch_and_save_fixtures(team):
    logger.info(f"Fetching fixtures for {team['name']}")

    for rnd in range(1, 21):
        url = f"{BASE_URL}{team['comp_id']}/{team['fixture_id']}/round/{rnd}"
        res = make_request(url)
        if not res:
            break

        soup = BeautifulSoup(res.text, "html.parser")
        games = soup.select(".fixture-details")

        for game_el in games:
            team_names = [el.text.strip() for el in game_el.select(".fixture-details-team-name")]
            if not any(team['name'] in name for name in team_names):
                continue

            game = extract_game_details(game_el)
            game["fixture_id"] = team['fixture_id']
            game["comp_id"] = team['comp_id']
            game["team_ref"] = db.collection("teams").document(f"team_{team['fixture_id']}")
            game["competition_ref"] = db.collection("competitions").document(f"comp_{team['comp_id']}")

            if "home_team" in game and team['name'] in game["home_team"].get("name", ""):
                game["home_team"]["id"] = f"team_{team['fixture_id']}"
            if "away_team" in game and team['name'] in game["away_team"].get("name", ""):
                game["away_team"]["id"] = f"team_{team['fixture_id']}"

            game_id = f"game_{team['fixture_id']}_{rnd}_{hash(str(game)) % 1000}"
            game["id"] = game_id

            game_ref = db.collection("games").document(game_id)
            if not game_ref.get().exists:
                game_ref.set(game)
                logger.info(f"Saved game: {game_id}")
        time.sleep(0.5)

# --- Main ---
def main():
    logger.info("=== Initial Fixture Poller ===")
    teams = load_mentone_teams()
    mentone_teams = [t for t in teams if t.get("is_home_club")]

    for team in mentone_teams:
        fetch_and_save_fixtures(team)

if __name__ == "__main__":
    main()
