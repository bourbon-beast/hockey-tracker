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
BASE_URL = "https://www.revolutionise.com.au/vichockey/games/"
MAX_ROUNDS = 20  # Maximum round number to check
REQUEST_TIMEOUT = 10  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
GAME_ID_REGEX = re.compile(r'/game/(\d+)')

# Initialize Firebase
try:
    cred = credentials.Certificate("./secrets/serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
except ValueError:
    # App already initialized
    pass

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

def generate_game_id(comp_id, fixture_id, round_num, home_team, away_team):
    """
    Generate a consistent, unique game ID.

    Args:
        comp_id: Competition ID
        fixture_id: Fixture/Grade ID
        round_num: Round number
        home_team: Home team name
        away_team: Away team name

    Returns:
        A unique game ID string
    """
    # Create a reproducible string that will be consistent for this game
    base = f"{comp_id}_{fixture_id}_{round_num}_{home_team}_{away_team}"

    # Create a hash of the base string to ensure uniqueness
    hash_object = hashlib.md5(base.encode())
    hash_str = hash_object.hexdigest()[:8]

    return f"game_{hash_str}"

def process_round_page(comp_id, fixture_id, round_num, mentone_teams):
    """
    Process a single round page and extract Mentone games.

    Args:
        comp_id: Competition ID
        fixture_id: Fixture/Grade ID
        round_num: Round number
        mentone_teams: Dict of Mentone teams keyed by team name

    Returns:
        List of game data dictionaries
    """
    round_url = f"{BASE_URL}{comp_id}/{fixture_id}/round/{round_num}"
    logger.info(f"Checking round URL: {round_url}")

    response = make_request(round_url)
    if not response:
        logger.warning(f"Failed to fetch round {round_num}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    # Look for game elements in all possible layouts
    game_elements = []

    # New layout
    new_layout = soup.select("div.fixture-details")
    if new_layout:
        game_elements.extend(new_layout)

    # Old layout
    old_layout = soup.select("div.card-body.font-size-sm")
    if old_layout:
        game_elements.extend(old_layout)

    # Try another potential selector - looking at parent card
    card_layout = soup.select("div.card.card-hover")
    if card_layout and not game_elements:
        game_elements.extend(card_layout)

    logger.info(f"Found {len(game_elements)} game elements on round {round_num} page")

    games = []

    # Add debugging for HTML content
    if len(game_elements) > 0:
        sample_game = game_elements[0]
        logger.debug(f"Sample game HTML structure: {sample_game}")

    # Process each game element
    for game_el in game_elements:
        try:
            # Log the raw text of the game element to debug
            logger.debug(f"Processing game: {game_el.get_text()[:100]}")
            # Extract teams from fixture
            # Try different selectors based on observed HTML structure
            team_els = []

            # New layout
            team_els = game_el.select(".fixture-details-team-name")

            # Old layout - this is what we're seeing in the HTML
            if not team_els or len(team_els) < 2:
                team_els = game_el.select("div.col-lg-3 a")

            # Very old layout - another possibility
            if not team_els or len(team_els) < 2:
                team_els = game_el.select(".text-center a")

            # Skip if we don't have at least two teams
            if len(team_els) < 2:
                logger.debug(f"Couldn't find two teams in game element: {game_el.get_text()[:100]}")
                continue

            # Get the first two team elements (home and away)
            home_team_name = team_els[0].text.strip()
            away_team_name = team_els[1].text.strip()

            # Print what we found for debugging
            logger.debug(f"Found teams: {home_team_name} vs {away_team_name}")

            # Check if Mentone is playing in this game
            # We need to be more flexible in how we match Mentone teams
            mentone_is_home = "Mentone" in home_team_name
            mentone_is_away = "Mentone" in away_team_name

            # If neither team has "Mentone" in the name, skip this game
            if not (mentone_is_home or mentone_is_away):
                logger.debug(f"No Mentone team in match: {home_team_name} vs {away_team_name}")
                continue

            logger.info(f"Found Mentone game: {home_team_name} vs {away_team_name}")

            # We found a Mentone game, let's extract details
            game = {}

            # Extract date and time
            # Try new layout first
            date_el = game_el.select_one(".fixture-details-date-long")

            if date_el:
                # New layout - format: "Monday, 14 April 2025 - 7:30 PM"
                date_text = date_el.text.strip()

                try:
                    date_parts = date_text.split(" - ")
                    date_str = date_parts[0]  # "Monday, 14 April 2025"
                    time_str = date_parts[1] if len(date_parts) > 1 else "12:00 PM"  # "7:30 PM"

                    # Parse date and time
                    datetime_str = f"{date_str} {time_str}"
                    game_date = datetime.strptime(datetime_str, "%A, %d %B %Y %I:%M %p")
                    game["date"] = game_date
                except ValueError:
                    # Try alternative format
                    try:
                        game_date = datetime.strptime(date_text, "%a %d %b %Y %I:%M %p")
                        game["date"] = game_date
                    except ValueError:
                        logger.warning(f"Could not parse date: {date_text}")
                        game["date"] = datetime.now()  # Fallback
            else:
                # Old layout
                datetime_el = game_el.select_one("div.col-md")
                if datetime_el:
                    lines = datetime_el.get_text("\n", strip=True).split("\n")
                    date_str = lines[0]
                    time_str = lines[1] if len(lines) > 1 else "12:00"

                    # Try different date formats
                    try:
                        game_date = datetime.strptime(f"{date_str} {time_str}", "%a %d %b %Y %I:%M %p")
                    except ValueError:
                        try:
                            game_date = datetime.strptime(f"{date_str} {time_str}", "%a %d %b %Y %H:%M")
                        except ValueError:
                            logger.warning(f"Could not parse date: {date_str} {time_str}")
                            game_date = datetime.now()  # Fallback

                    game["date"] = game_date
                else:
                    game["date"] = datetime.now()  # Fallback if no date found

            # Extract venue
            # Try new layout
            venue_el = game_el.select_one(".fixture-details-venue")

            # If not found, try old layout
            if not venue_el:
                venue_el = game_el.select_one("div.col-md a")

            game["venue"] = venue_el.text.strip() if venue_el else "Unknown Venue"

            # Extract club info for both teams
            home_club_name, home_club_id = extract_club_info(home_team_name)
            away_club_name, away_club_id = extract_club_info(away_team_name)

            # Find team IDs - we need to be more flexible
            home_team_id = None
            away_team_id = None

            # Helper function to find the best matching team
            def find_best_match(team_name):
                if "Mentone" not in team_name:
                    return None

                # Try exact match first
                for name, data in mentone_teams.items():
                    if name == team_name:
                        return data["id"]

                # Try simple match - e.g., if "Mentone Hockey Club" is in team name
                for name, data in mentone_teams.items():
                    if "Mentone" in team_name and data["fixture_id"] == int(fixture_id):
                        return data["id"]

                # As a fallback, just use the first team with matching fixture_id
                for name, data in mentone_teams.items():
                    if data["fixture_id"] == int(fixture_id):
                        logger.warning(f"Using fallback team match for {team_name} → {name}")
                        return data["id"]

                return None

            # If Mentone is home, find the best match
            if mentone_is_home:
                home_team_id = find_best_match(home_team_name)
                if home_team_id:
                    logger.debug(f"Matched home team {home_team_name} to ID {home_team_id}")

            # If Mentone is away, find the best match
            if mentone_is_away:
                away_team_id = find_best_match(away_team_name)
                if away_team_id:
                    logger.debug(f"Matched away team {away_team_name} to ID {away_team_id}")

            # Set up team data
            game["home_team"] = {
                "name": home_team_name,
                "id": home_team_id,
                "club": home_club_name,
                "club_id": home_club_id
            }

            game["away_team"] = {
                "name": away_team_name,
                "id": away_team_id,
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
                if (game["home_team"].get("score") is not None and
                        game["away_team"].get("score") is not None):
                    game["status"] = "completed"
                else:
                    game["status"] = "in_progress"
            else:
                game["status"] = "scheduled"

            # Metadata
            game["round"] = round_num
            game["comp_id"] = comp_id
            game["fixture_id"] = fixture_id

            # Generate proper references based on new database structure
            # Create a list of team references
            team_refs = []
            if home_team_id:
                team_refs.append(db.collection("teams").document(home_team_id))
            if away_team_id:
                team_refs.append(db.collection("teams").document(away_team_id))

            game["team_refs"] = team_refs

            # Club references
            club_refs = [
                db.collection("clubs").document(home_club_id),
                db.collection("clubs").document(away_club_id)
            ]
            game["club_refs"] = club_refs

            # Add other references
            game["competition_ref"] = db.collection("competitions").document(comp_id)
            game["grade_ref"] = db.collection("grades").document(fixture_id)

            # Empty player stats object for future use
            game["player_stats"] = {}

            # Details URL and extract game ID from it
            details_btn = game_el.select_one("a.btn-outline-primary")
            if details_btn and "href" in details_btn.attrs:
                game_url = details_btn["href"]
                game["url"] = game_url

                # Extract game ID from URL - URLs look like https://www.hockeyvictoria.org.au/game/2047239
                game_id_match = GAME_ID_REGEX.search(game_url)
                if game_id_match:
                    game_id = game_id_match.group(1)
                    game["id"] = game_id
                    logger.info(f"Extracted game ID {game_id} from URL {game_url}")
                else:
                    # If we can't extract the ID, use our hash-based ID as fallback
                    game_id = generate_game_id(comp_id, fixture_id, round_num, home_team_name, away_team_name)
                    game["id"] = game_id
                    logger.warning(f"Could not extract game ID from URL {game_url}, using generated ID {game_id}")
            else:
                # If no details button, use our hash-based ID
                game_id = generate_game_id(comp_id, fixture_id, round_num, home_team_name, away_team_name)
                game["id"] = game_id
                logger.warning(f"No details button found for game, using generated ID {game_id}")

            games.append(game)
            logger.info(f"Found Mentone game in round {round_num}: {home_team_name} vs {away_team_name}")

        except Exception as e:
            logger.error(f"Error parsing game: {e}", exc_info=True)
            continue

    return games

def fetch_mentone_games(competitions, mentone_teams):
    """
    Fetch all Mentone games from all competitions.

    Args:
        competitions: List of competitions to check
        mentone_teams: Dict of Mentone teams

    Returns:
        List of game data dictionaries
    """
    all_games = []

    for comp in competitions:
        comp_id = comp["id"]
        fixture_id = comp["fixture_id"]
        comp_name = comp["name"]

        logger.info(f"Checking competition: {comp_name}")

        # Find all games for this competition/fixture across all rounds
        for round_num in range(1, MAX_ROUNDS + 1):
            games = process_round_page(comp_id, fixture_id, round_num, mentone_teams)
            all_games.extend(games)

            # If no games found for this round, we might be at the end of available data
            if not games and round_num > 1:
                logger.info(f"No games found for round {round_num}, stopping search for {comp_name}")
                break

            # Be nice to the server
            time.sleep(0.5)

    return all_games

def update_games_in_firestore(games):
    """
    Update games in Firestore.

    Args:
        games: List of game data dictionaries

    Returns:
        Tuple of (updates, creates) count
    """
    updates = 0
    creates = 0

    for game in games:
        game_id = game["id"]
        game_ref = db.collection("games").document(game_id)

        # Check if game already exists
        existing_game = game_ref.get()

        if existing_game.exists:
            # Update existing game
            existing_data = existing_game.to_dict()

            # Don't overwrite scores if they're already set and we don't have scores
            if "score" in existing_data.get("home_team", {}) and "score" not in game.get("home_team", {}):
                game["home_team"]["score"] = existing_data["home_team"]["score"]

            if "score" in existing_data.get("away_team", {}) and "score" not in game.get("away_team", {}):
                game["away_team"]["score"] = existing_data["away_team"]["score"]

            # Don't change completed status back to in_progress
            if existing_data.get("status") == "completed" and game.get("status") == "in_progress":
                game["status"] = "completed"

            # Preserve existing player stats
            if "player_stats" in existing_data and existing_data["player_stats"]:
                game["player_stats"] = existing_data["player_stats"]

            # Update timestamps
            game["updated_at"] = firestore.SERVER_TIMESTAMP

            # Update game
            game_ref.update(game)
            updates += 1
            logger.info(f"Updated game: {game_id}")
        else:
            # Create new game
            game["created_at"] = firestore.SERVER_TIMESTAMP
            game["updated_at"] = firestore.SERVER_TIMESTAMP

            # Create game
            game_ref.set(game)
            creates += 1
            logger.info(f"Created game: {game_id}")

    return updates, creates

def main():
    """
    Main function to fetch and update Mentone games.
    """
    start_time = time.time()
    logger.info("Starting Mentone Hockey Club fixture poller")

    try:
        # Get all Mentone teams
        mentone_teams = {}
        team_query = db.collection("teams").where("club", "==", "Mentone").stream()

        for doc in team_query:
            team_data = doc.to_dict()
            team_data["id"] = doc.id  # Ensure ID is included
            mentone_teams[team_data["name"]] = team_data
            logger.debug(f"Found team: {team_data['name']} (ID: {doc.id}, Fixture: {team_data.get('fixture_id')})")

        logger.info(f"Found {len(mentone_teams)} Mentone teams")

        if not mentone_teams:
            logger.warning("No Mentone teams found in the database. Exiting.")
            return

        # Get all competitions that have Mentone teams
        comp_ids = set()
        fixture_ids = set()

        for team_name, team_data in mentone_teams.items():
            comp_ids.add(str(team_data["comp_id"]))
            fixture_ids.add(str(team_data["fixture_id"]))

            # Also check all fixture IDs for this team
            fixture_id = str(team_data["fixture_id"])
            logger.info(f"Checking rounds for fixture ID {fixture_id} ({team_data['name']})")

            # Fetch games for each fixture ID
            all_games = []
            for round_num in range(1, MAX_ROUNDS + 1):
                comp_id = str(team_data["comp_id"])
                round_games = process_round_page(comp_id, fixture_id, round_num, mentone_teams)

                if round_games:
                    all_games.extend(round_games)
                elif round_num > 1:
                    # No games in this round, might have reached the end
                    logger.info(f"No games found in round {round_num} for fixture {fixture_id}, stopping search")
                    break

                # Be nice to the server
                time.sleep(0.5)

            logger.info(f"Found {len(all_games)} Mentone games for fixture {fixture_id}")

            # Update Firestore
            updates, creates = update_games_in_firestore(all_games)
            logger.info(f"Updated {updates} games, created {creates} games for fixture {fixture_id}")

        elapsed_time = time.time() - start_time
        logger.info(f"Fixture update complete in {elapsed_time:.2f} seconds: {creates} new games, {updates} updated games")

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)

if __name__ == "__main__":
    main()


# Enable debug logging
logging.getLogger().setLevel(logging.DEBUG)

# Initialize Firebase
try:
    cred = credentials.Certificate("../secrets/serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
except ValueError:
    # App already initialized
    pass

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

def generate_game_id(comp_id, fixture_id, round_num, home_team, away_team):
    """
    Generate a consistent, unique game ID.

    Args:
        comp_id: Competition ID
        fixture_id: Fixture/Grade ID
        round_num: Round number
        home_team: Home team name
        away_team: Away team name

    Returns:
        A unique game ID string
    """
    # Create a reproducible string that will be consistent for this game
    base = f"{comp_id}_{fixture_id}_{round_num}_{home_team}_{away_team}"

    # Create a hash of the base string to ensure uniqueness
    hash_object = hashlib.md5(base.encode())
    hash_str = hash_object.hexdigest()[:8]

    return f"game_{hash_str}"

def process_round_page(comp_id, fixture_id, round_num, mentone_teams):
    """
    Process a single round page and extract Mentone games.

    Args:
        comp_id: Competition ID
        fixture_id: Fixture/Grade ID
        round_num: Round number
        mentone_teams: Dict of Mentone teams keyed by team name

    Returns:
        List of game data dictionaries
    """
    round_url = f"{BASE_URL}{comp_id}/{fixture_id}/round/{round_num}"
    logger.info(f"Checking round URL: {round_url}")

    response = make_request(round_url)
    if not response:
        logger.warning(f"Failed to fetch round {round_num}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    # Look for game elements in all possible layouts
    game_elements = []

    # New layout
    new_layout = soup.select("div.fixture-details")
    if new_layout:
        game_elements.extend(new_layout)

    # Old layout
    old_layout = soup.select("div.card-body.font-size-sm")
    if old_layout:
        game_elements.extend(old_layout)

    # Try another potential selector - looking at parent card
    card_layout = soup.select("div.card.card-hover")
    if card_layout and not game_elements:
        game_elements.extend(card_layout)

    logger.info(f"Found {len(game_elements)} game elements on round {round_num} page")

    games = []

    # Add debugging for HTML content
    if len(game_elements) > 0:
        sample_game = game_elements[0]
        logger.debug(f"Sample game HTML structure: {sample_game}")

    # Process each game element
    for game_el in game_elements:
        try:
            # Log the raw text of the game element to debug
            logger.debug(f"Processing game: {game_el.get_text()[:100]}")
            # Extract teams from fixture
            # Try different selectors based on observed HTML structure
            team_els = []

            # New layout
            team_els = game_el.select(".fixture-details-team-name")

            # Old layout - this is what we're seeing in the HTML
            if not team_els or len(team_els) < 2:
                team_els = game_el.select("div.col-lg-3 a")

            # Very old layout - another possibility
            if not team_els or len(team_els) < 2:
                team_els = game_el.select(".text-center a")

            # Skip if we don't have at least two teams
            if len(team_els) < 2:
                logger.debug(f"Couldn't find two teams in game element: {game_el.get_text()[:100]}")
                continue

            # Get the first two team elements (home and away)
            home_team_name = team_els[0].text.strip()
            away_team_name = team_els[1].text.strip()

            # Print what we found for debugging
            logger.debug(f"Found teams: {home_team_name} vs {away_team_name}")

            # Check if Mentone is playing in this game
            # We need to be more flexible in how we match Mentone teams
            mentone_is_home = "Mentone" in home_team_name
            mentone_is_away = "Mentone" in away_team_name

            # If neither team has "Mentone" in the name, skip this game
            if not (mentone_is_home or mentone_is_away):
                logger.debug(f"No Mentone team in match: {home_team_name} vs {away_team_name}")
                continue

            logger.info(f"Found Mentone game: {home_team_name} vs {away_team_name}")

            # We found a Mentone game, let's extract details
            game = {}

            # Extract date and time
            # Try new layout first
            date_el = game_el.select_one(".fixture-details-date-long")

            if date_el:
                # New layout - format: "Monday, 14 April 2025 - 7:30 PM"
                date_text = date_el.text.strip()

                try:
                    date_parts = date_text.split(" - ")
                    date_str = date_parts[0]  # "Monday, 14 April 2025"
                    time_str = date_parts[1] if len(date_parts) > 1 else "12:00 PM"  # "7:30 PM"

                    # Parse date and time
                    datetime_str = f"{date_str} {time_str}"
                    game_date = datetime.strptime(datetime_str, "%A, %d %B %Y %I:%M %p")
                    game["date"] = game_date
                except ValueError:
                    # Try alternative format
                    try:
                        game_date = datetime.strptime(date_text, "%a %d %b %Y %I:%M %p")
                        game["date"] = game_date
                    except ValueError:
                        logger.warning(f"Could not parse date: {date_text}")
                        game["date"] = datetime.now()  # Fallback
            else:
                # Old layout
                datetime_el = game_el.select_one("div.col-md")
                if datetime_el:
                    lines = datetime_el.get_text("\n", strip=True).split("\n")
                    date_str = lines[0]
                    time_str = lines[1] if len(lines) > 1 else "12:00"

                    # Try different date formats
                    try:
                        game_date = datetime.strptime(f"{date_str} {time_str}", "%a %d %b %Y %I:%M %p")
                    except ValueError:
                        try:
                            game_date = datetime.strptime(f"{date_str} {time_str}", "%a %d %b %Y %H:%M")
                        except ValueError:
                            logger.warning(f"Could not parse date: {date_str} {time_str}")
                            game_date = datetime.now()  # Fallback

                    game["date"] = game_date
                else:
                    game["date"] = datetime.now()  # Fallback if no date found

            # Extract venue
            # Try new layout
            venue_el = game_el.select_one(".fixture-details-venue")

            # If not found, try old layout
            if not venue_el:
                venue_el = game_el.select_one("div.col-md a")

            game["venue"] = venue_el.text.strip() if venue_el else "Unknown Venue"

            # Extract club info for both teams
            home_club_name, home_club_id = extract_club_info(home_team_name)
            away_club_name, away_club_id = extract_club_info(away_team_name)

            # Find team IDs - we need to be more flexible
            home_team_id = None
            away_team_id = None

            # Helper function to find the best matching team
            def find_best_match(team_name):
                if "Mentone" not in team_name:
                    return None

                # Try exact match first
                for name, data in mentone_teams.items():
                    if name == team_name:
                        return data["id"]

                # Try simple match - e.g., if "Mentone Hockey Club" is in team name
                for name, data in mentone_teams.items():
                    if "Mentone" in team_name and data["fixture_id"] == int(fixture_id):
                        return data["id"]

                # As a fallback, just use the first team with matching fixture_id
                for name, data in mentone_teams.items():
                    if data["fixture_id"] == int(fixture_id):
                        logger.warning(f"Using fallback team match for {team_name} → {name}")
                        return data["id"]

                return None

            # If Mentone is home, find the best match
            if mentone_is_home:
                home_team_id = find_best_match(home_team_name)
                if home_team_id:
                    logger.debug(f"Matched home team {home_team_name} to ID {home_team_id}")

            # If Mentone is away, find the best match
            if mentone_is_away:
                away_team_id = find_best_match(away_team_name)
                if away_team_id:
                    logger.debug(f"Matched away team {away_team_name} to ID {away_team_id}")

            # Set up team data
            game["home_team"] = {
                "name": home_team_name,
                "id": home_team_id,
                "club": home_club_name,
                "club_id": home_club_id
            }

            game["away_team"] = {
                "name": away_team_name,
                "id": away_team_id,
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
                if (game["home_team"].get("score") is not None and
                        game["away_team"].get("score") is not None):
                    game["status"] = "completed"
                else:
                    game["status"] = "in_progress"
            else:
                game["status"] = "scheduled"

            # Metadata
            game["round"] = round_num
            game["comp_id"] = comp_id
            game["fixture_id"] = fixture_id

            # Generate proper references based on new database structure
            # Create a list of team references
            team_refs = []
            if home_team_id:
                team_refs.append(db.collection("teams").document(home_team_id))
            if away_team_id:
                team_refs.append(db.collection("teams").document(away_team_id))

            game["team_refs"] = team_refs

            # Club references
            club_refs = [
                db.collection("clubs").document(home_club_id),
                db.collection("clubs").document(away_club_id)
            ]
            game["club_refs"] = club_refs

            # Add other references
            game["competition_ref"] = db.collection("competitions").document(comp_id)
            game["grade_ref"] = db.collection("grades").document(fixture_id)

            # Empty player stats object for future use
            game["player_stats"] = {}

            # Generate game ID
            game["id"] = generate_game_id(
                comp_id,
                fixture_id,
                round_num,
                home_team_name,
                away_team_name
            )

            games.append(game)
            logger.info(f"Found Mentone game in round {round_num}: {home_team_name} vs {away_team_name}")

        except Exception as e:
            logger.error(f"Error parsing game: {e}", exc_info=True)
            continue

    return games

def fetch_mentone_games(competitions, mentone_teams):
    """
    Fetch all Mentone games from all competitions.

    Args:
        competitions: List of competitions to check
        mentone_teams: Dict of Mentone teams

    Returns:
        List of game data dictionaries
    """
    all_games = []

    for comp in competitions:
        comp_id = comp["id"]
        fixture_id = comp["fixture_id"]
        comp_name = comp["name"]

        logger.info(f"Checking competition: {comp_name}")

        # Find all games for this competition/fixture across all rounds
        for round_num in range(1, MAX_ROUNDS + 1):
            games = process_round_page(comp_id, fixture_id, round_num, mentone_teams)
            all_games.extend(games)

            # If no games found for this round, we might be at the end of available data
            if not games and round_num > 1:
                logger.info(f"No games found for round {round_num}, stopping search for {comp_name}")
                break

            # Be nice to the server
            time.sleep(0.5)

    return all_games

def update_games_in_firestore(games):
    """
    Update games in Firestore.

    Args:
        games: List of game data dictionaries

    Returns:
        Tuple of (updates, creates) count
    """
    updates = 0
    creates = 0

    for game in games:
        game_id = game["id"]
        game_ref = db.collection("games").document(game_id)

        # Check if game already exists
        existing_game = game_ref.get()

        if existing_game.exists:
            # Update existing game
            existing_data = existing_game.to_dict()

            # Don't overwrite scores if they're already set and we don't have scores
            if "score" in existing_data.get("home_team", {}) and "score" not in game.get("home_team", {}):
                game["home_team"]["score"] = existing_data["home_team"]["score"]

            if "score" in existing_data.get("away_team", {}) and "score" not in game.get("away_team", {}):
                game["away_team"]["score"] = existing_data["away_team"]["score"]

            # Don't change completed status back to in_progress
            if existing_data.get("status") == "completed" and game.get("status") == "in_progress":
                game["status"] = "completed"

            # Preserve existing player stats
            if "player_stats" in existing_data and existing_data["player_stats"]:
                game["player_stats"] = existing_data["player_stats"]

            # Update timestamps
            game["updated_at"] = firestore.SERVER_TIMESTAMP

            # Update game
            game_ref.update(game)
            updates += 1
            logger.info(f"Updated game: {game_id}")
        else:
            # Create new game
            game["created_at"] = firestore.SERVER_TIMESTAMP
            game["updated_at"] = firestore.SERVER_TIMESTAMP

            # Create game
            game_ref.set(game)
            creates += 1
            logger.info(f"Created game: {game_id}")

    return updates, creates

def main():
    """
    Main function to fetch and update Mentone games.
    """
    start_time = time.time()
    logger.info("Starting Mentone Hockey Club fixture poller")

    try:
        # Get all Mentone teams
        mentone_teams = {}
        team_query = db.collection("teams").where("club", "==", "Mentone").stream()

        for doc in team_query:
            team_data = doc.to_dict()
            team_data["id"] = doc.id  # Ensure ID is included
            mentone_teams[team_data["name"]] = team_data

        logger.info(f"Found {len(mentone_teams)} Mentone teams")

        if not mentone_teams:
            logger.warning("No Mentone teams found in the database. Exiting.")
            return

        # Get all competitions that have Mentone teams
        comp_ids = set()
        fixture_ids = set()

        for team_name, team_data in mentone_teams.items():
            comp_ids.add(str(team_data["comp_id"]))
            fixture_ids.add(str(team_data["fixture_id"]))

        # Get competition data
        competitions = []
        for comp_id in comp_ids:
            comp_doc = db.collection("competitions").document(comp_id).get()
            if comp_doc.exists:
                comp_data = comp_doc.to_dict()
                comp_data["id"] = comp_id
                competitions.append(comp_data)

        logger.info(f"Found {len(competitions)} competitions with Mentone teams")

        # Fetch all Mentone games
        all_games = fetch_mentone_games(competitions, mentone_teams)
        logger.info(f"Found {len(all_games)} Mentone games")

        # Update Firestore
        updates, creates = update_games_in_firestore(all_games)

        elapsed_time = time.time() - start_time
        logger.info(f"Fixture update complete in {elapsed_time:.2f} seconds: {creates} new games, {updates} updated games")

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)

if __name__ == "__main__":
    main()