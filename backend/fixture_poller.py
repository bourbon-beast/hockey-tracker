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
    game_elements = soup.select(".fixture-details")
    logger.info(f"Found {len(game_elements)} games on round {round_num} page")

    # Look for the team name in each game
    for game_el in game_elements:
        teams_el = game_el.select_one(".fixture-details-teams")
        if not teams_el:
            continue

        team_names = [el.text.strip() for el in teams_el.select(".fixture-details-team-name")]

        # Check if our team is in this game
        if any(team_name in name for name in team_names):
            logger.info(f"Found game for {team_name} in round {round_num}")

            game = {}

            # Parse date/time
            date_el = game_el.select_one(".fixture-details-date-long")
            if date_el:
                try:
                    date_parts = date_el.text.strip().split(" - ")
                    date_str = date_parts[0]
                    time_str = date_parts[1] if len(date_parts) > 1 else "12:00 PM"
                    game_date = datetime.strptime(f"{date_str} {time_str}", "%A, %d %B %Y %I:%M %p")
                    game["date"] = game_date
                except Exception as e:
                    logger.warning(f"Date parsing error: {e}")
                    game["date"] = None

            # Parse venue
            venue_el = game_el.select_one(".fixture-details-venue")
            if venue_el:
                game["venue"] = venue_el.text.strip()

            # Round is already known
            game["round"] = round_num

            # Parse teams and scores
            home_el = teams_el.select_one(".fixture-details-team-home")
            away_el = teams_el.select_one(".fixture-details-team-away")

            if home_el and away_el:
                # Home team
                home_name = home_el.select_one(".fixture-details-team-name").text.strip()
                home_score_el = home_el.select_one(".fixture-details-team-score")
                home_score = None
                if home_score_el and home_score_el.text.strip() and home_score_el.text.strip() != "-":
                    try:
                        home_score = int(home_score_el.text.strip())
                    except:
                        pass

                # Away team
                away_name = away_el.select_one(".fixture-details-team-name").text.strip()
                away_score_el = away_el.select_one(".fixture-details-team-score")
                away_score = None
                if away_score_el and away_score_el.text.strip() and away_score_el.text.strip() != "-":
                    try:
                        away_score = int(away_score_el.text.strip())
                    except:
                        pass

                # Determine if Mentone is home or away
                is_home = team_name in home_name

                # Set team data
                game["home_team"] = {
                    "name": home_name,
                    "score": home_score,
                    "id": team_id if is_home else None,
                    "club": "Mentone" if is_home else None
                }

                game["away_team"] = {
                    "name": away_name,
                    "score": away_score,
                    "id": team_id if not is_home else None,
                    "club": "Mentone" if not is_home else None
                }

                # Game status
                if home_score is not None and away_score is not None:
                    game["status"] = "completed"
                elif game["date"] and game["date"] < datetime.now():
                    game["status"] = "in_progress"
                else:
                    game["status"] = "scheduled"

                # Add metadata
                game["comp_id"] = comp_id
                game["fixture_id"] = fixture_id
                game["team_ref"] = db.collection("teams").document(team_id)
                game["competition_ref"] = db.collection("competitions").document(f"comp_senior_{comp_id}")
                game["grade_ref"] = db.collection("grades").document(f"grade_senior_{fixture_id}")
                game["player_stats"] = {}

                # Create ID
                game_id = f"game_{team_id}_{round_num}_{hash(str(game))%1000}"
                game["id"] = game_id

                return game

    return None

def fetch_team_games(team_data):
    """Fetch games for a team by checking each round page"""
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
        time.sleep(0.5)  # Be nice to the server

    logger.info(f"Found {len(games)} games for {team_name}")
    return games

def main():
    logger.info("Starting Mentone Hockey Club fixture fetcher")

    # Get teams from Firestore
    teams = []
    for doc in db.collection("teams").stream():
        team_data = doc.to_dict()
        team_data['id'] = doc.id
        if team_data.get('club') == 'Mentone':
            teams.append(team_data)

    logger.info(f"Found {len(teams)} Mentone teams")

    # Fetch and save games
    all_games = []
    for team in teams:
        team_games = fetch_team_games(team)
        all_games.extend(team_games)
        logger.info(f"Found {len(team_games)} games for {team['name']}")

    # Save to Firestore
    for game in all_games:
        db.collection("games").document(game["id"]).set(game)

    logger.info(f"Saved {len(all_games)} games to Firestore")

if __name__ == "__main__":
    main()