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

# Regex patterns
COMP_FIXTURE_REGEX = re.compile(r"/games/(\d+)/(\d+)")
TEAM_ID_REGEX = re.compile(r"/games/team/(\d+)/(\d+)")
GAME_ID_REGEX = re.compile(r'/game/(\d+)$')

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

# Initialize Firebase
cred = credentials.Certificate("../secrets/serviceAccountKey.json")
firebase_admin.initialize_app(cred)
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

def extract_club_info(team_name):
    """
    Extract club name from team name.

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

    # Generate simpler club_id
    club_id = club_name.lower().replace(" ", "_").replace("-", "_")

    return club_name, club_id

def create_team_name(comp_name, club="Mentone"):
    """
    Create a descriptive team name from competition name.

    Args:
        comp_name (str): Competition name
        club (str): Club name prefix

    Returns:
        str: Formatted team name
    """
    # Strip year and clean up competition name
    name = comp_name.split(' - ')[0] if ' - ' in comp_name else comp_name

    # Create a descriptive team name
    return f"{club} - {name}"

def create_or_get_club(club_name, club_id):
    """
    Create a club in Firestore if it doesn't exist.

    Args:
        club_name (str): Club name
        club_id (str): Club ID

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
    comp_id = comp["comp_id"]
    fixture_id = comp["fixture_id"]
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

    # Create the Firestore document - use actual comp_id as document ID
    comp_ref = db.collection("competitions").document(comp_id)

    comp_data = {
        "id": comp_id,
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

def extract_team_ids_from_page(soup, comp_id):
    """
    Extract team IDs from a competition page.

    Args:
        soup (BeautifulSoup): Parsed HTML
        comp_id (str): Competition ID

    Returns:
        dict: Dictionary mapping team names to their IDs
    """
    team_info = {}

    # Look for team links in the page
    for a in soup.find_all("a"):
        href = a.get("href", "")
        text = a.text.strip()

        # Check if this is a team link
        team_match = TEAM_ID_REGEX.search(href)
        if team_match and is_valid_team(text):
            link_comp_id, team_id = team_match.groups()

            # Only use if the competition ID matches
            if link_comp_id == comp_id:
                team_info[text] = team_id
                logger.debug(f"Found team ID for {text}: {team_id}")

    return team_info

def find_team_id_on_fixture_page(comp_id, fixture_id, team_name):
    """
    Find a team's ID by looking at the fixture page.

    Args:
        comp_id (str): Competition ID
        fixture_id (str): Fixture/Grade ID
        team_name (str): Team name to find

    Returns:
        str or None: Team ID if found
    """
    url = f"https://www.hockeyvictoria.org.au/games/{comp_id}/{fixture_id}/round/1"
    response = make_request(url)

    if not response:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    team_info = extract_team_ids_from_page(soup, comp_id)

    # Look for exact match
    if team_name in team_info:
        return team_info[team_name]

    # Try partial match if exact match not found
    for name, team_id in team_info.items():
        if team_name.lower() in name.lower() or name.lower() in team_name.lower():
            logger.warning(f"Using partial match for {team_name}: found {name} with ID {team_id}")
            return team_id

    return None

def find_and_create_teams(competitions):
    """
    Scan competitions to find team IDs and create in Firestore.

    Args:
        competitions (list): List of competition dictionaries

    Returns:
        list: Created teams
    """
    logger.info(f"Scanning {len(competitions)} competitions for teams...")
    teams = []
    seen = set()
    processed_count = 0

    # Create all competitions first
    comp_refs = {}
    for comp in competitions:
        comp_ref = create_competition(comp)
        comp_refs[comp["comp_id"]] = comp_ref

    # Create all grades (fixtures)
    for comp in competitions:
        # Use actual fixture_id as the document ID
        fixture_id = comp["fixture_id"]
        fixture_ref = db.collection("grades").document(fixture_id)

        comp_id = comp["comp_id"]
        comp_name = comp["name"]
        team_type, gender = classify_team(comp_name)

        fixture_data = {
            "id": fixture_id,
            "name": comp_name,
            "comp_id": comp_id,
            "type": team_type,
            "gender": gender,
            "competition_ref": comp_refs[comp_id],
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP
        }

        fixture_ref.set(fixture_data)
        logger.info(f"Created grade: {comp_name} ({fixture_id})")

    # Now process teams
    for comp in competitions:
        processed_count += 1
        comp_name = comp['name']
        comp_id = comp['comp_id']
        fixture_id = comp['fixture_id']
        round_url = f"https://www.hockeyvictoria.org.au/games/{comp_id}/{fixture_id}/round/1"

        logger.info(f"[{processed_count}/{len(competitions)}] Checking {comp_name} at {round_url}")

        response = make_request(round_url)
        if not response:
            continue

        soup = BeautifulSoup(response.text, "html.parser")

        # Extract teams and their IDs from the page
        team_info = extract_team_ids_from_page(soup, comp_id)

        # Also look for team names in the fixtures that might not have direct links
        fixture_teams = set()
        for div in soup.select(".fixture-details-team-name"):
            text = div.text.strip()
            if is_valid_team(text):
                fixture_teams.add(text)

        # Combine both sources
        all_teams = set(team_info.keys()) | fixture_teams

        team_type, gender = classify_team(comp_name)

        # Create/update teams
        for raw_team_name in all_teams:
            # Extract club information
            club_name, club_id = extract_club_info(raw_team_name)

            # Create a proper descriptive team name using the competition name
            # This ensures teams are named like "Mentone - Women's Premier League"
            # instead of just "Mentone Hockey Club"
            competition_part = comp_name.split(' - ')[0] if ' - ' in comp_name else comp_name
            team_name = f"{club_name} - {competition_part}"

            # Skip if we've already seen this team
            key = (team_name, fixture_id)
            if key in seen:
                continue

            seen.add(key)

            # Get team ID - either from our extraction or try to find it
            team_id = team_info.get(raw_team_name)

            if not team_id:
                # Try to find the team ID using other methods
                team_id = find_team_id_on_fixture_page(comp_id, fixture_id, raw_team_name)

            if not team_id:
                # If still not found, create a fallback ID
                logger.warning(f"Could not find actual team ID for {team_name}, using fallback ID")
                team_id = f"{fixture_id}_{club_id}"

            # Create or get club reference
            club_ref = create_or_get_club(club_name, club_id)

            # Create team data
            team_data = {
                "id": team_id,
                "name": team_name,  # Use our formatted team name with competition
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
                logger.info(f"Found Mentone team: {team_name} (ID: {team_id}, Type: {team_type}, Gender: {gender})")
            else:
                logger.debug(f"Found team: {team_name} (ID: {team_id})")

    logger.info(f"Team discovery complete. Found {len(teams)} teams total.")
    return teams

def generate_sample_players(teams):
    """
    Generate sample players for each team (just one per team).

    Args:
        teams (list): List of team data
    """
    logger.info(f"Creating one sample player for each Mentone team")

    # Sample player names
    mens_names = ["James Smith", "Michael Brown", "Robert Jones", "David Miller"]
    womens_names = ["Jennifer Smith", "Lisa Brown", "Mary Jones", "Sarah Miller"]

    # Create 1 player per team
    players_created = 0
    for team in teams:
        # Skip non-Mentone teams
        if team.get("is_home_club", False) == False:
            continue

        # Use appropriate name based on gender
        if team["gender"] == "Men":
            name = mens_names[0]
        else:
            name = womens_names[0]

        # Create simple player ID
        player_id = f"{team['id']}_player1"

        # Create player data
        player_data = {
            "id": player_id,
            "name": name,
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
                "goals": 2,
                "assists": 3,
                "games_played": 5,
                "yellow_cards": 0,
                "red_cards": 0,
            }
        }

        # Save to Firestore
        db.collection("players").document(player_id).set(player_data)
        players_created += 1

    logger.info(f"Created {players_created} sample players")

def generate_sample_games(teams):
    """
    Generate sample games for teams (just one per team).

    Args:
        teams (list): List of team data
    """
    logger.info(f"Creating one sample game for each Mentone team")

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

    # Set of sample venues
    venues = ["Mentone Grammar Playing Fields", "State Netball Hockey Centre"]

    games_created = 0

    for mentone_team in mentone_teams:
        # Find appropriate opponents (same gender, same competition level)
        suitable_opponents = [team for team in opponent_teams
                              if team["gender"] == mentone_team["gender"]
                              and team["comp_id"] == mentone_team["comp_id"]]

        # If no suitable opponents, use any opponent of same gender
        if not suitable_opponents:
            suitable_opponents = [team for team in opponent_teams if team["gender"] == mentone_team["gender"]]

        # If still no opponents, use any opponent
        if not suitable_opponents:
            suitable_opponents = opponent_teams

        # If we have an opponent, create one sample game
        if suitable_opponents:
            opponent = suitable_opponents[0]

            # Create a proper game ID using the pattern "1_fixture_id" + timestamp
            # Actual hockey victoria IDs are numerical, so we'll simulate that format
            timestamp = int(time.time()) % 10000  # Last 4 digits of current timestamp
            game_id = f"1{mentone_team['fixture_id']}{timestamp}"

            # Sample date - a Saturday in the future
            game_date = datetime(2025, 4, 5)

            # Create the game URL as would be found on Hockey Victoria
            game_url = f"https://www.hockeyvictoria.org.au/game/{game_id}"

            # Create sample game
            game_data = {
                "id": game_id,
                "url": game_url,
                "fixture_id": mentone_team["fixture_id"],
                "comp_id": mentone_team["comp_id"],
                "round": 1,
                "date": game_date,
                "venue": venues[0],
                "status": "scheduled",
                "home_team": {
                    "id": mentone_team["id"],
                    "name": mentone_team["name"],
                    "club": mentone_team["club"],
                    "club_id": mentone_team["club_id"]
                },
                "away_team": {
                    "id": opponent["id"],
                    "name": opponent["name"],
                    "club": opponent["club"],
                    "club_id": opponent["club_id"]
                },
                "team_refs": [
                    db.collection("teams").document(mentone_team["id"]),
                    db.collection("teams").document(opponent["id"])
                ],
                "club_refs": [
                    db.collection("clubs").document(mentone_team["club_id"]),
                    db.collection("clubs").document(opponent["club_id"])
                ],
                "competition_ref": db.collection("competitions").document(mentone_team["comp_id"]),
                "grade_ref": db.collection("grades").document(mentone_team["fixture_id"]),
                "created_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP
            }

            # Save to Firestore
            db.collection("games").document(game_id).set(game_data)
            games_created += 1

    logger.info(f"Created {games_created} sample games")

def process_round_page(comp_id, fixture_id, round_num, team_id, team_name):
    """Process a single round page and extract games for a team"""
    round_url = f"https://www.hockeyvictoria.org.au/games/{comp_id}/{fixture_id}/round/{round_num}"
    logger.info(f"Checking round URL: {round_url}")

    response = make_request(round_url)
    if not response:
        logger.warning(f"Failed to fetch round {round_num}: Status code error")
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
            game["competition_ref"] = db.collection("competitions").document(comp_id)
            game["grade_ref"] = db.collection("grades").document(fixture_id)
            game["player_stats"] = {}

            # Details URL and extract game ID
            details_btn = game_el.select_one("a.btn-outline-primary")
            if details_btn and "href" in details_btn.attrs:
                game_url = details_btn["href"]
                game["url"] = game_url

                # Extract the actual game ID from the URL
                # URLs typically look like: https://www.hockeyvictoria.org.au/game/2048530
                game_id_match = GAME_ID_REGEX.search(game_url)
                if game_id_match:
                    game_id = game_id_match.group(1)
                    game["id"] = game_id
                else:
                    # Fallback if we can't extract the ID from URL
                    game_id = f"game_{team_id}_{round_num}_{int(time.time())}"
                    game["id"] = game_id
            else:
                # Fallback if there's no details button
                game_id = f"game_{team_id}_{round_num}_{int(time.time())}"
                game["id"] = game_id

            return game

        except Exception as e:
            logger.error(f"Error parsing game: {e}")
            continue

    return None

def fetch_team_games(team_data, max_rounds=10):
    """
    Fetch games for a specific team.

    Args:
        team_data (dict): Team data
        max_rounds (int): Maximum number of rounds to check

    Returns:
        list: Found games
    """
    team_id = team_data['id']
    comp_id = team_data['comp_id']
    fixture_id = team_data['fixture_id']
    team_name = team_data['name']

    logger.info(f"Fetching games for team: {team_name}")
    games = []
    for round_num in range(1, max_rounds + 1):
        game = process_round_page(comp_id, fixture_id, round_num, team_id, team_name)
        if game:
            games.append(game)
        time.sleep(0.5)  # Be nice to the server

    logger.info(f"Found {len(games)} games for {team_name}")
    return games

def cleanup_firestore():
    """
    Delete all existing data in Firestore.
    """
    logger.info("Cleaning up Firestore collections...")

    collections_to_clean = ["clubs", "competitions", "grades", "teams", "games", "players", "settings"]

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

        # Create sample players - just one per team
        generate_sample_players(teams)

        # Create sample games - just one per team
        generate_sample_games(teams)

        # Create settings
        create_settings()

        # Try to fetch some real games for Mentone teams
        mentone_teams = [team for team in teams if team.get("is_home_club", False)]
        if mentone_teams:
            logger.info(f"Attempting to fetch real games for {len(mentone_teams)} Mentone teams")
            games_found = 0
            # Just try one team to see if it works
            for team in mentone_teams[:2]:  # Limit to first 2 teams to avoid overloading
                team_games = fetch_team_games(team, max_rounds=3)  # Only check first 3 rounds
                for game in team_games:
                    db.collection("games").document(game["id"]).set(game)
                    games_found += 1
            logger.info(f"Successfully found and added {games_found} real games from Hockey Victoria")

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)

    elapsed_time = time.time() - start_time
    logger.info(f"Script completed in {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    main()