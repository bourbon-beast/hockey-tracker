import firebase_admin
from firebase_admin import credentials, firestore
import requests
from bs4 import BeautifulSoup
import re
import logging
import time
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler(f"fixture_fetch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
                              logging.StreamHandler()])
logger = logging.getLogger(__name__)

# Constants
BASE_URL = "https://www.hockeyvictoria.org.au/games/"
MAX_ROUNDS = 20  # Maximum round number to check

# Initialize Firebase
cred = credentials.Certificate("./secrets/serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

def process_round_page(comp_id, fixture_id, round_num, team_id, team_name):
    """Process a single round page and extract Mentone games"""
    round_url = f"{BASE_URL}{comp_id}/{fixture_id}/round/{round_num}"
    logger.info(f"Checking round URL: {round_url}")

    response = requests.get(round_url)
    if not response.ok:
        logger.warning(f"Failed to fetch round {round_num}: {response.status_code}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    game_elements = soup.select("div.card-body.font-size-sm")
    logger.info(f"Found {len(game_elements)} games on round {round_num} page")

    for game_el in game_elements:
        team_links = game_el.select("div.col-lg-3 a")
        if len(team_links) != 2:
            continue

        hrefs = [a.get("href", "") for a in team_links]
        team_match = any(f"/games/team/{comp_id}/{team_id.split('_')[-1]}" in href for href in hrefs)
        if not team_match:
            continue

        try:
            game = {}

            # Extract date and time
            datetime_el = game_el.select_one("div.col-md")
            if datetime_el:
                lines = datetime_el.get_text("\n", strip=True).split("\n")
                date_str = lines[0]
                time_str = lines[1] if len(lines) > 1 else "12:00"
                try:
                    game_date = datetime.strptime(f"{date_str} {time_str}", "%a %d %b %Y %H:%M")
                except:
                    game_date = datetime.strptime(f"{date_str} {time_str}", "%a %d %b %Y %I:%M %p")
                game["date"] = game_date

            # Venue
            venue_link = game_el.select_one("div.col-md a")
            game["venue"] = venue_link.text.strip() if venue_link else None

            # Teams
            game["home_team"] = {
                "name": team_links[0].text.strip(),
                "id": None,
                "club": None
            }
            game["away_team"] = {
                "name": team_links[1].text.strip(),
                "id": None,
                "club": None
            }

            # Determine if our team is home or away
            if f"/games/team/{comp_id}/{team_id.split('_')[-1]}" in hrefs[0]:
                game["home_team"]["id"] = team_id
                game["home_team"]["club"] = "Mentone"
            else:
                game["away_team"]["id"] = team_id
                game["away_team"]["club"] = "Mentone"

            # Game status
            now = datetime.now()
            if game["date"] < now:
                game["status"] = "in_progress"
            else:
                game["status"] = "scheduled"

            # Metadata
            game["round"] = round_num
            game["comp_id"] = comp_id
            game["fixture_id"] = fixture_id
            game["team_ref"] = db.collection("teams").document(team_id)
            game["competition_ref"] = db.collection("competitions").document(f"comp_senior_{comp_id}")
            game["grade_ref"] = db.collection("grades").document(f"grade_senior_{fixture_id}")
            game["player_stats"] = {}

            # Details URL
            details_btn = game_el.select_one("a.btn-outline-primary")
            game["url"] = details_btn["href"] if details_btn else None

            # Game ID
            game_id = f"game_{team_id}_{round_num}_{hash(str(game))%1000}"
            game["id"] = game_id

            return game

        except Exception as e:
            logger.error(f"Error parsing game: {e}")
            continue

    return None

def fetch_team_games(team_data):
    team_id = team_data['id']
    comp_id = team_data['comp_id']
    fixture_id = team_data['fixture_id']
    team_name = team_data['name']

    logger.info(f"Fetching games for team: {team_name}")
    games = []
    for round_num in range(1, MAX_ROUNDS + 1):
        game = process_round_page(comp_id, fixture_id, round_num, team_id, team_name)
        if game:
            games.append(game)
        time.sleep(0.5)
    logger.info(f"Found {len(games)} games for {team_name}")
    return games

def main():
    logger.info("Starting Mentone Hockey Club fixture fetcher")
    teams = []
    for doc in db.collection("teams").stream():
        team_data = doc.to_dict()
        team_data['id'] = doc.id
        if team_data.get('club') == 'Mentone':
            teams.append(team_data)

    logger.info(f"Found {len(teams)} Mentone teams")
    all_games = []
    for team in teams:
        team_games = fetch_team_games(team)
        all_games.extend(team_games)
        logger.info(f"Found {len(team_games)} games for {team['name']}")

    for game in all_games:
        db.collection("games").document(game["id"]).set(game)

    logger.info(f"Saved {len(all_games)} games to Firestore")

if __name__ == "__main__":
    main()
