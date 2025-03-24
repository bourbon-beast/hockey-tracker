import firebase_admin
from firebase_admin import credentials, firestore
import requests
from bs4 import BeautifulSoup
import re
import json
import logging
import time
from urllib.parse import urljoin
from datetime import datetime, timedelta
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"fresh_start_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
BASE_URL = "https://www.revolutionise.com.au/vichockey/games/"
TEAM_FILTER = "Mentone"
OUTPUT_FILE = "mentone_teams.json"
REQUEST_TIMEOUT = 10  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# Initialize Firebase
cred = credentials.Certificate("../secrets/serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Regex for fixture links: /games/{comp_id}/{fixture_id}
COMP_FIXTURE_REGEX = re.compile(r"/games/(\d+)/(\d+)")

# Gender/type classification based on naming
GENDER_MAP = {
    "men": "Men",
    "women": "Women",
    "boys": "Boys",
    "girls": "Girls",
    "mixed": "Mixed"
}

TYPE_KEYWORDS = {
    "senior": "Senior",
    "junior": "Junior",
    "midweek": "Midweek",
    "masters": "Masters",
    "outdoor": "Outdoor",
    "indoor": "Indoor"
}

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

def extract_club_info(team_name):
    """
    Extract club name from team name and create a club ID.

    Args:
        team_name (str): Team name (e.g. "Mentone - Men's Vic League 1")

    Returns:
        tuple: (club_name, club_id)
    """
    if " - " in team_name:
        club_name = team_name.split(" - ")[0].strip()
    else:
        # Handle case where there's no delimiter
        club_name = team_name.split()[0]

    # Generate club_id - lowercase, underscores
    club_id = f"club_{club_name.lower().replace(' ', '_').replace('-', '_')}"

    return club_name, club_id

def create_or_get_club(club_name, club_id):
    """
    Create a club in Firestore if it doesn't exist.

    Args:
        club_name (str): Club name
        club_id (str): Generated club ID

    Returns:
        DocumentReference: Reference to the club document
    """
    club_ref = db.collection("clubs").document(club_id)

    # Check if club exists
    if not club_ref.get().exists:
        logger.info(f"Creating new club: {club_name} ({club_id})")

        # Default to Mentone fields for Mentone, generic for others
        is_mentone = club_name.lower() == "mentone"
        club_data = {
            "id": club_id,
            "name": f"{club_name} Hockey Club" if is_mentone else club_name,
            "short_name": club_name,
            "code": "".join([word[0] for word in club_name.split()]).upper(),
            "location": "Melbourne, Victoria" if is_mentone else None,
            "home_venue": "Mentone Grammar Playing Fields" if is_mentone else None,
            "primary_color": "#0066cc" if is_mentone else "#333333",
            "secondary_color": "#ffffff",
            "active": True,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
            "is_home_club": is_mentone
        }

        club_ref.set(club_data)

    return club_ref

def classify_team(comp_name):
    """
    Classify a team by type and gender based on competition name.

    Args:
        comp_name (str): Competition name

    Returns:
        tuple: (team_type, gender)
    """
    comp_name_lower = comp_name.lower()

    # Determine team type
    team_type = "Unknown"
    for keyword, value in TYPE_KEYWORDS.items():
        if keyword in comp_name_lower:
            team_type = value
            break

    # Special case handling - identify senior/junior/masters competitions
    if "premier league" in comp_name_lower or "vic league" in comp_name_lower or "pennant" in comp_name_lower:
        team_type = "Senior"
    elif "u12" in comp_name_lower or "u14" in comp_name_lower or "u16" in comp_name_lower or "u18" in comp_name_lower:
        team_type = "Junior"
    elif "masters" in comp_name_lower or "35+" in comp_name_lower or "45+" in comp_name_lower or "60+" in comp_name_lower:
        team_type = "Midweek"

    # Determine gender from competition name
    if "women's" in comp_name_lower or "women" in comp_name_lower:
        gender = "Women"
    elif "men's" in comp_name_lower or "men" in comp_name_lower:
        gender = "Men"
    else:
        # Fall back to keyword checking if not explicitly men's/women's
        gender = "Unknown"
        for keyword, value in GENDER_MAP.items():
            if keyword in comp_name_lower:
                gender = value
                break

    return team_type, gender

def is_valid_team(name):
    """
    Filter out false positives like venue names.

    Args:
        name (str): Team name

    Returns:
        bool: True if valid team, False otherwise
    """
    invalid_keywords = ["playing fields", "grammar"]
    return all(kw not in name.lower() for kw in invalid_keywords) and "hockey club" in name.lower()

def create_team_name(comp_name, club="Mentone"):
    """
    Create a team name from competition name.

    Args:
        comp_name (str): Competition name
        club (str): Club name prefix

    Returns:
        str: Formatted team name
    """
    # Strip year and clean up
    name = comp_name.split(' - ')[0] if ' - ' in comp_name else comp_name
    return f"{club} - {name}"

def get_competition_blocks():
    """
    Scrape the main page to get all competition blocks.

    Returns:
        list: List of competition dictionaries
    """
    logger.info("Discovering competitions from main page...")
    res = make_request(BASE_URL)
    if not res:
        logger.error(f"Failed to get main page: {BASE_URL}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    competitions = []
    current_heading = ""

    # Find competition headings and links
    headings = soup.find_all("h2")
    logger.info(f"Found {len(headings)} competition heading sections")

    for div in soup.select("div.px-4.py-2.border-top"):
        heading_el = div.find_previous("h2")
        if heading_el:
            current_heading = heading_el.text.strip()

        a = div.find("a")
        if a and a.get("href"):
            match = COMP_FIXTURE_REGEX.search(a["href"])
            if match:
                comp_id, fixture_id = match.groups()
                comp_name = a.text.strip()
                competitions.append({
                    "name": comp_name,
                    "comp_heading": current_heading,
                    "comp_id": comp_id,
                    "fixture_id": fixture_id,
                    "url": urljoin("https://www.hockeyvictoria.org.au", a["href"])
                })
                logger.debug(f"Added competition: {comp_name} ({comp_id}/{fixture_id})")

    logger.info(f"Found {len(competitions)} competitions")
    return competitions

def create_competition(comp):
    """
    Create a competition in Firestore.

    Args:
        comp (dict): Competition data

    Returns:
        DocumentReference: Reference to the competition document
    """
    comp_id = int(comp["comp_id"])
    fixture_id = int(comp["fixture_id"])
    comp_name = comp.get("comp_heading", comp["name"])

    # Determine competition type
    comp_type = "Senior"  # Default type
    if "junior" in comp_name.lower() or "u12" in comp_name.lower() or "u14" in comp_name.lower() or "u16" in comp_name.lower():
        comp_type = "Junior"
    elif "masters" in comp_name.lower() or "35+" in comp_name.lower() or "45+" in comp_name.lower() or "60+" in comp_name.lower():
        comp_type = "Midweek/Masters"

    # Extract season info
    season = "2025"  # Default
    if " - " in comp_name:
        parts = comp_name.split(" - ")
        if len(parts) > 1 and parts[1].strip().isdigit():
            season = parts[1].strip()

    # Create the Firestore document
    comp_ref = db.collection("competitions").document(f"comp_{comp_id}")

    comp_data = {
        "id": f"comp_{comp_id}",
        "comp_id": comp_id,
        "name": comp_name,
        "type": comp_type,
        "season": season,
        "fixture_id": fixture_id,
        "start_date": firestore.SERVER_TIMESTAMP,
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
        "active": True
    }

    comp_ref.set(comp_data)
    logger.info(f"Created competition: {comp_name} ({comp_id})")

    return comp_ref

def find_and_create_teams(competitions):
    """
    Scan competitions to find Mentone teams and create in Firestore.

    Args:
        competitions (list): List of competition dictionaries

    Returns:
        list: Created teams
    """
    logger.info(f"Scanning {len(competitions)} competitions for teams...")
    teams = []
    seen = set()
    processed_count = 0

    # First, create all competitions
    comp_refs = {}
    for comp in competitions:
        comp_ref = create_competition(comp)
        comp_refs[int(comp["comp_id"])] = comp_ref

    for comp in competitions:
        processed_count += 1
        comp_name = comp['name']
        comp_id = int(comp['comp_id'])
        fixture_id = int(comp['fixture_id'])
        round_url = f"https://www.hockeyvictoria.org.au/games/{comp['comp_id']}/{comp['fixture_id']}/round/1"

        logger.info(f"[{processed_count}/{len(competitions)}] Checking {comp_name} at {round_url}")

        response = make_request(round_url)
        if not response:
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        found_mentone_team = False

        # Extract all teams from this fixture to build club database
        all_teams = set()
        for a in soup.find_all("a"):
            text = a.text.strip()
            if "hockey club" in text.lower() and all(kw not in text.lower() for kw in ["playing fields", "grammar"]):
                all_teams.add(text)

        # Create clubs and teams for all found teams
        for team_name in all_teams:
            club_name, club_id = extract_club_info(team_name)

            # Skip if we've already seen this team/fixture combo
            key = (team_name, fixture_id)
            if key in seen:
                continue

            seen.add(key)

            # Create or get club
            club_ref = create_or_get_club(club_name, club_id)

            # Determine team type and gender
            team_type, gender = classify_team(comp_name)

            # Create team ID
            team_id = f"team_{fixture_id}_{club_id}"

            # Create team data
            team_data = {
                "id": team_id,
                "name": team_name,
                "fixture_id": fixture_id,
                "comp_id": comp_id,
                "comp_name": comp_name,
                "type": team_type,
                "gender": gender,
                "club": club_name,
                "club_id": club_id,
                "club_ref": club_ref,
                "is_home_club": club_name.lower() == "mentone",
                "created_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
                "competition_ref": comp_refs.get(comp_id)
            }

            # Add to teams list
            teams.append(team_data)

            # Save to Firestore
            db.collection("teams").document(team_id).set(team_data)

            # Log Mentone teams specifically
            if TEAM_FILTER.lower() in team_name.lower():
                found_mentone_team = True
                logger.info(f"Found Mentone team: {team_name} ({team_type}, {gender})")
            else:
                logger.debug(f"Found team: {team_name} ({team_type}, {gender})")

        if not found_mentone_team:
            logger.debug(f"No Mentone teams found in {comp_name}")

    logger.info(f"Team discovery complete. Found {len(teams)} teams total.")
    return teams

def generate_sample_players(teams):
    """
    Generate sample players for each team.

    Args:
        teams (list): List of team data
    """
    logger.info(f"Creating sample players for {len(teams)} teams")

    # Sample player names
    mens_names = ["James Smith", "Michael Brown", "Robert Jones", "David Miller",
                  "John Wilson", "Thomas Moore", "Daniel Taylor", "Paul Anderson",
                  "Andrew Thomas", "Joshua White", "William Harris", "Christopher Jackson",
                  "Matthew Clark", "Richard Lewis", "Charles Walker", "Joseph Young"]

    womens_names = ["Jennifer Smith", "Lisa Brown", "Mary Jones", "Sarah Miller",
                    "Jessica Wilson", "Emily Moore", "Emma Taylor", "Olivia Anderson",
                    "Isabella Thomas", "Sophia White", "Charlotte Harris", "Amelia Jackson",
                    "Ava Clark", "Mia Lewis", "Elizabeth Walker", "Abigail Young"]

    # Create 5-10 players per team
    for team in teams:
        # Skip non-Mentone teams to avoid creating too many players
        if team.get("is_home_club", False) == False:
            continue

        # Use appropriate names based on gender
        if team["gender"] == "Men":
            names = mens_names
        else:
            names = womens_names

        # Determine number of players (5-10)
        num_players = min(len(names), 10)

        for i in range(num_players):
            player_id = f"player_{team['id']}_{i+1}"

            # Create player data
            player_data = {
                "id": player_id,
                "name": names[i],
                "teams": [team["id"]],
                "team_refs": [db.collection("teams").document(team["id"])],
                "gender": team["gender"],
                "club_id": team["club_id"],
                "club_ref": db.collection("clubs").document(team["club_id"]),
                "primary_team_id": team["id"],
                "primary_team_ref": db.collection("teams").document(team["id"]),
                "created_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
                "stats": {
                    "goals": i,
                    "assists": i * 2,
                    "games_played": 5,
                    "yellow_cards": 0 if i < 8 else 1,
                    "red_cards": 0,
                }
            }

            # Save to Firestore
            db.collection("players").document(player_id).set(player_data)

        logger.info(f"Created {num_players} players for team {team['name']}")

def generate_sample_games(teams):
    """
    Generate sample games for teams.

    Args:
        teams (list): List of team data
    """
    logger.info(f"Creating sample games for teams")

    # Get Mentone teams
    mentone_teams = [team for team in teams if team.get("is_home_club", False)]

    if not mentone_teams:
        logger.warning("No Mentone teams found, cannot create sample games")
        return

    # Get opponent teams (non-Mentone)
    opponent_teams = [team for team in teams if not team.get("is_home_club", False)]

    if not opponent_teams:
        logger.warning("No opponent teams found, using Mentone teams as opponents")
        opponent_teams = mentone_teams

    # Generate 5 rounds of fixtures
    venues = ["Mentone Grammar Playing Fields", "State Netball Hockey Centre",
              "Hawthorn Hockey Club", "Footscray Hockey Club", "Doncaster Hockey Club"]

    games_created = 0

    for mentone_team in mentone_teams:
        # Find appropriate opponents (same gender, same competition level if possible)
        suitable_opponents = [team for team in opponent_teams
                              if team["gender"] == mentone_team["gender"]
                              and team["comp_id"] == mentone_team["comp_id"]]

        # If no suitable opponents, use any opponent of the same gender
        if not suitable_opponents:
            suitable_opponents = [team for team in opponent_teams if team["gender"] == mentone_team["gender"]]

        # If still no opponents, use any opponent
        if not suitable_opponents:
            suitable_opponents = opponent_teams

        # Create 5 home games and 5 away games
        for round_num in range(1, 6):
            # Home game
            if suitable_opponents:
                opponent = suitable_opponents[round_num % len(suitable_opponents)]

                game_id = f"game_{mentone_team['id']}_{opponent['id']}_{round_num}_home"

                # Game date (Saturday of each week starting April 2025)
                game_date = datetime(2025, 4, 5) + timedelta(days=(round_num-1)*7)

                # Random scores for completed games (first 3 rounds)
                status = "completed" if round_num <= 3 else "scheduled"
                home_score = round_num * 2 if status == "completed" else None
                away_score = round_num if status == "completed" else None

                game_data = {
                    "id": game_id,
                    "fixture_id": mentone_team["fixture_id"],
                    "comp_id": mentone_team["comp_id"],
                    "round": round_num,
                    "date": game_date,
                    "venue": venues[round_num % len(venues)],
                    "status": status,
                    "home_team": {
                        "id": mentone_team["id"],
                        "name": mentone_team["name"],
                        "club": mentone_team["club"],
                        "club_id": mentone_team["club_id"],
                        "score": home_score
                    },
                    "away_team": {
                        "id": opponent["id"],
                        "name": opponent["name"],
                        "club": opponent["club"],
                        "club_id": opponent["club_id"],
                        "score": away_score
                    },
                    "team_refs": [
                        db.collection("teams").document(mentone_team["id"]),
                        db.collection("teams").document(opponent["id"])
                    ],
                    "club_refs": [
                        db.collection("clubs").document(mentone_team["club_id"]),
                        db.collection("clubs").document(opponent["club_id"])
                    ],
                    "competition_ref": db.collection("competitions").document(f"comp_{mentone_team['comp_id']}"),
                    "created_at": firestore.SERVER_TIMESTAMP,
                    "updated_at": firestore.SERVER_TIMESTAMP
                }

                # Save to Firestore
                db.collection("games").document(game_id).set(game_data)
                games_created += 1

            # Away game (2 weeks after home game)
            if suitable_opponents:
                opponent = suitable_opponents[(round_num + 2) % len(suitable_opponents)]

                game_id = f"game_{opponent['id']}_{mentone_team['id']}_{round_num}_away"

                # Game date (Saturday of each week starting April 2025, 1 week after home)
                game_date = datetime(2025, 4, 12) + timedelta(days=(round_num-1)*7)

                # Random scores for completed games (first 3 rounds)
                status = "completed" if round_num <= 3 else "scheduled"
                home_score = round_num if status == "completed" else None
                away_score = round_num * 2 if status == "completed" else None

                game_data = {
                    "id": game_id,
                    "fixture_id": mentone_team["fixture_id"],
                    "comp_id": mentone_team["comp_id"],
                    "round": round_num + 5,  # Return fixtures are rounds 6-10
                    "date": game_date,
                    "venue": venues[(round_num + 2) % len(venues)],
                    "status": status,
                    "home_team": {
                        "id": opponent["id"],
                        "name": opponent["name"],
                        "club": opponent["club"],
                        "club_id": opponent["club_id"],
                        "score": home_score
                    },
                    "away_team": {
                        "id": mentone_team["id"],
                        "name": mentone_team["name"],
                        "club": mentone_team["club"],
                        "club_id": mentone_team["club_id"],
                        "score": away_score
                    },
                    "team_refs": [
                        db.collection("teams").document(opponent["id"]),
                        db.collection("teams").document(mentone_team["id"])
                    ],
                    "club_refs": [
                        db.collection("clubs").document(opponent["club_id"]),
                        db.collection("clubs").document(mentone_team["club_id"])
                    ],
                    "competition_ref": db.collection("competitions").document(f"comp_{mentone_team['comp_id']}"),
                    "created_at": firestore.SERVER_TIMESTAMP,
                    "updated_at": firestore.SERVER_TIMESTAMP
                }

                # Save to Firestore
                db.collection("games").document(game_id).set(game_data)
                games_created += 1

    logger.info(f"Created {games_created} sample games")

def cleanup_firestore():
    """
    Delete all existing data in Firestore.
    """
    logger.info("Cleaning up Firestore collections...")

    collections_to_clean = ["clubs", "competitions", "teams", "games", "players", "settings"]

    for collection_name in collections_to_clean:
        docs = db.collection(collection_name).stream()
        count = 0

        for doc in docs:
            doc.reference.delete()
            count += 1

        logger.info(f"Deleted {count} documents from {collection_name}")

def create_settings():
    """
    Create default settings in Firestore.
    """
    logger.info("Creating settings...")

    settings_data = {
        "id": "email_settings",
        "pre_game_hours": 24,
        "weekly_summary_day": "Sunday",
        "weekly_summary_time": "20:00",
        "admin_emails": ["admin@mentone.com"],
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP
    }

    db.collection("settings").document("email_settings").set(settings_data)
    logger.info("Created email settings")

def save_teams_to_json(teams, output_file=OUTPUT_FILE):
    """
    Save discovered teams to a JSON file.

    Args:
        teams (list): List of team dictionaries
        output_file (str): Output file path
    """
    try:
        # Remove references as they're not JSON serializable
        cleaned_teams = []
        for team in teams:
            team_copy = team.copy()
            if 'club_ref' in team_copy:
                del team_copy['club_ref']
            if 'competition_ref' in team_copy:
                del team_copy['competition_ref']
            cleaned_teams.append(team_copy)

        with open(output_file, "w") as f:
            json.dump(cleaned_teams, f, indent=2)
        logger.info(f"Successfully saved {len(teams)} teams to {output_file}")
    except Exception as e:
        logger.error(f"Failed to save teams to {output_file}: {e}")

def main():
    """Main function to run the builder script."""
    start_time = time.time()
    logger.info(f"=== Mentone Hockey Club Fresh Start Builder ===")
    logger.info(f"This will delete all existing data and recreate the database")

    try:
        # Clean up existing data
        cleanup_firestore()

        # Get competitions
        comps = get_competition_blocks()
        if not comps:
            logger.error("No competitions found. Exiting.")
            return

        # Find and create teams
        teams = find_and_create_teams(comps)

        # Save teams to JSON
        save_teams_to_json(teams)

        # Create sample players
        generate_sample_players(teams)

        # Create sample games
        generate_sample_games(teams)

        # Create settings
        create_settings()

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)

    elapsed_time = time.time() - start_time
    logger.info(f"Script completed in {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    main()