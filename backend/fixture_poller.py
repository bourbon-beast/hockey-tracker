import firebase_admin
from firebase_admin import credentials, firestore
import requests
from bs4 import BeautifulSoup
import re
import logging
import time
from datetime import datetime
import hashlib

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler(f"fixture_fetch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
                              logging.StreamHandler()])
logger = logging.getLogger(__name__)

# Constants
BASE_URL = "https://www.hockeyvictoria.org.au/games/"
MAX_ROUNDS = 20  # Maximum round number to check
REQUEST_TIMEOUT = 10  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# Initialize Firebase
cred = credentials.Certificate("./secrets/serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

def make_request(url, retry_count=0):
    """
    Make an HTTP request with retries and error handling.
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

def extract_club_info(team_name):
    """
    Extract club name and ID from team name.
    """
    if " - " in team_name:
        club_name = team_name.split(" - ")[0].strip()
    else:
        # Handle case where there's no delimiter
        club_name = team_name.split()[0]

    # Generate club_id consistent with fresh_start.py
    club_id = club_name.lower().replace(" ", "_").replace("-", "_")

    return club_name, club_id

def generate_game_id(team_id, fixture_id, round_num, opponent_id=None):
    """
    Generate a consistent, unique game ID.
    """
    if opponent_id:
        base = f"{fixture_id}_{team_id}_{round_num}_{opponent_id}"
    else:
        base = f"{fixture_id}_{team_id}_{round_num}_{datetime.now().strftime('%Y%m%d')}"

    # Create a hash of the base string to ensure uniqueness
    hash_object = hashlib.md5(base.encode())
    hash_str = hash_object.hexdigest()[:6]

    return f"game_{hash_str}"

def process_round_page(comp_id, fixture_id, round_num, team_data):
    """
    Process a single round page and extract team games.

    Args:
        comp_id: Competition ID
        fixture_id: Fixture/Grade ID
        round_num: Round number
        team_data: Full team document data

    Returns:
        Game data dictionary or None
    """
    team_id = team_data["id"]
    team_name = team_data["name"]
    team_type = team_data["type"].lower()

    round_url = f"{BASE_URL}{comp_id}/{fixture_id}/round/{round_num}"
    logger.info(f"Checking round URL: {round_url}")

    response = make_request(round_url)
    if not response:
        logger.warning(f"Failed to fetch round {round_num}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    game_elements = soup.select("div.card-body.font-size-sm, div.fixture-details")
    logger.info(f"Found {len(game_elements)} game elements on round {round_num} page")

    # Flexibility - check both old and new HTML structures
    for game_el in game_elements:
        # Check if team is playing in this game
        team_els = game_el.select("div.col-lg-3 a, .fixture-details-team-name")

        # Skip if we don't have at least two teams
        if len(team_els) < 2:
            continue

        team_names = [el.text.strip() for el in team_els]

        # Check if our team is playing
        if team_name not in team_names:
            continue

        try:
            game = {}

            # Extract date and time
            date_text = ""
            time_text = "12:00"  # Default time

            # Try different selectors for date (handling different HTML structures)
            date_el = game_el.select_one("div.col-md, .fixture-details-date-long")
            if date_el:
                text = date_el.get_text("\n", strip=True)
                lines = text.split("\n")

                if " - " in text:  # Format: "Monday, 14 April 2025 - 7:30 PM"
                    parts = text.split(" - ")
                    date_text = parts[0]
                    time_text = parts[1] if len(parts) > 1 else time_text
                else:  # Format: "Mon 14 Apr 2025\n12:00 PM"
                    date_text = lines[0]
                    time_text = lines[1] if len(lines) > 1 else time_text

                # Try different date formats
                try:
                    game_date = datetime.strptime(f"{date_text} {time_text}", "%A, %d %B %Y %I:%M %p")
                except ValueError:
                    try:
                        game_date = datetime.strptime(f"{date_text} {time_text}", "%a %d %b %Y %I:%M %p")
                    except ValueError:
                        try:
                            game_date = datetime.strptime(f"{date_text} {time_text}", "%a %d %b %Y %H:%M")
                        except ValueError:
                            logger.warning(f"Could not parse date: {date_text} {time_text}")
                            game_date = datetime.now()  # Fallback

                game["date"] = game_date

            # Extract venue
            venue_el = game_el.select_one("div.col-md a, .fixture-details-venue")
            game["venue"] = venue_el.text.strip() if venue_el else "Unknown Venue"

            # Extract teams and determine home/away
            home_team_name = team_names[0]
            away_team_name = team_names[1] if len(team_names) > 1 else "Unknown Team"

            # Figure out which is our team
            is_home = (home_team_name == team_name)

            # Get club information for both teams
            home_club_name, home_club_id = extract_club_info(home_team_name)
            away_club_name, away_club_id = extract_club_info(away_team_name)

            # Try to find team IDs for opponent (may not exist yet)
            opponent_team_id = None
            if not is_home:
                # Query Firestore for the opponent team
                opponent_teams = db.collection("teams").where("name", "==", home_team_name).limit(1).stream()
                for doc in opponent_teams:
                    opponent_team_id = doc.id
                    break
            else:
                # Query Firestore for the opponent team
                opponent_teams = db.collection("teams").where("name", "==", away_team_name).limit(1).stream()
                for doc in opponent_teams:
                    opponent_team_id = doc.id
                    break

            # Set up team data
            game["home_team"] = {
                "name": home_team_name,
                "id": team_id if is_home else opponent_team_id,
                "club": home_club_name,
                "club_id": home_club_id
            }

            game["away_team"] = {
                "name": away_team_name,
                "id": team_id if not is_home else opponent_team_id,
                "club": away_club_name,
                "club_id": away_club_id
            }

            # Look for scores
            score_els = game_el.select(".fixture-details-team-score")
            if len(score_els) >= 2:
                home_score_text = score_els[0].text.strip()
                away_score_text = score_els[1].text.strip()

                if home_score_text and home_score_text != "-":
                    try:
                        game["home_team"]["score"] = int(home_score_text)
                    except ValueError:
                        pass

                if away_score_text and away_score_text != "-":
                    try:
                        game["away_team"]["score"] = int(away_score_text)
                    except ValueError:
                        pass

            # Determine game status
            now = datetime.now()
            if game.get("date", now) < now:
                if "score" in game["home_team"] and "score" in game["away_team"]:
                    game["status"] = "completed"
                else:
                    game["status"] = "in_progress"
            else:
                game["status"] = "scheduled"

            # Metadata
            game["round"] = round_num
            game["comp_id"] = comp_id
            game["fixture_id"] = fixture_id

            # Generate proper references based on team_type from fresh_start.py
            game["team_ref"] = db.collection("teams").document(team_id)
            game["competition_ref"] = db.collection("competitions").document(comp_id)
            game["grade_ref"] = db.collection("grades").document(fixture_id)

            # Add team and club references
            game["team_refs"] = [db.collection("teams").document(team_id)]
            if opponent_team_id:
                game["team_refs"].append(db.collection("teams").document(opponent_team_id))

            # Add club references
            game["club_refs"] = [
                db.collection("clubs").document(home_club_id),
                db.collection("clubs").document(away_club_id)
            ]

            game["player_stats"] = {}

            # Details URL - try to extract from HTML
            details_btn = game_el.select_one("a.btn-outline-primary")
            game["url"] = details_btn["href"] if details_btn and "href" in details_btn.attrs else None

            # Generate game ID
            game["id"] = generate_game_id(team_id, fixture_id, round_num, opponent_team_id)

            return game

        except Exception as e:
            logger.error(f"Error parsing game: {e}", exc_info=True)
            continue

    return None

def fetch_team_games(team_data):
    """
    Fetch games for a specific team.
    """
    team_id = team_data['id']
    comp_id = team_data['comp_id']
    fixture_id = team_data['fixture_id']
    team_name = team_data['name']

    logger.info(f"Fetching games for team: {team_name}")
    games = []

    for round_num in range(1, MAX_ROUNDS + 1):
        game = process_round_page(comp_id, fixture_id, round_num, team_data)
        if game:
            games.append(game)
            logger.info(f"Found game for {team_name} in round {round_num}")
        time.sleep(0.5)  # Polite delay between requests

    logger.info(f"Found {len(games)} games for {team_name}")
    return games

def update_existing_games(games):
    """
    Update existing games in Firestore if they exist, otherwise create them.
    """
    updates = 0
    creates = 0

    for game in games:
        game_ref = db.collection("games").document(game["id"])
        existing_game = game_ref.get()

        if existing_game.exists:
            # Preserve existing data that might be manually entered
            existing_data = existing_game.to_dict()

            # Don't overwrite scores if they're already set
            if "score" in existing_data.get("home_team", {}) and "score" not in game.get("home_team", {}):
                game["home_team"]["score"] = existing_data["home_team"]["score"]

            if "score" in existing_data.get("away_team", {}) and "score" not in game.get("away_team", {}):
                game["away_team"]["score"] = existing_data["away_team"]["score"]

            # Don't change completed status back to in_progress
            if existing_data.get("status") == "completed" and game.get("status") == "in_progress":
                game["status"] = "completed"

            # Update the existing document
            game["updated_at"] = firestore.SERVER_TIMESTAMP
            game_ref.update(game)
            updates += 1
        else:
            # Create new game document
            game["created_at"] = firestore.SERVER_TIMESTAMP
            game["updated_at"] = firestore.SERVER_TIMESTAMP
            game_ref.set(game)
            creates += 1

    return updates, creates

def main():
    """
    Main function to fetch and update games.
    """
    logger.info("Starting Mentone Hockey Club fixture fetcher")

    # Get all Mentone teams
    teams = []
    team_query = db.collection("teams").where("club", "==", "Mentone").stream()

    for doc in team_query:
        team_data = doc.to_dict()
        team_data['id'] = doc.id
        teams.append(team_data)

    logger.info(f"Found {len(teams)} Mentone teams")

    if not teams:
        logger.warning("No Mentone teams found in the database. Exiting.")
        return

    all_games = []
    for team in teams:
        team_games = fetch_team_games(team)
        all_games.extend(team_games)

    # Update Firestore
    updates, creates = update_existing_games(all_games)

    logger.info(f"Fixture update complete: {creates} new games, {updates} updated games")

if __name__ == "__main__":
    main()