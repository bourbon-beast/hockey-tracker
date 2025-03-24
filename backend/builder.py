import requests
from bs4 import BeautifulSoup
import re
import json
import logging
import time
import os
from urllib.parse import urljoin
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"builder_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
BASE_URL = "https://www.revolutionise.com.au/vichockey/games/"
TEAM_FILTER = "Mentone"
REQUEST_TIMEOUT = 10  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# This will store the discovered teams
mentone_teams = []

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

# Initialize Firebase
def initialize_firebase():
    """Initialize Firebase connection"""
    if not firebase_admin._apps:
        try:
            # Try to find the service account key
            key_locations = [
                "serviceAccountKey.json",
                "../secrets/serviceAccountKey.json",
                "secrets/serviceAccountKey.json"
            ]

            key_path = None
            for loc in key_locations:
                if os.path.exists(loc):
                    key_path = loc
                    break

            if key_path:
                cred = credentials.Certificate(key_path)
                firebase_admin.initialize_app(cred)
                logger.info(f"Firebase initialized with key from {key_path}")
            else:
                # Use default credentials (for development environment)
                firebase_admin.initialize_app()
                logger.info("Firebase initialized with default credentials")

        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            raise

    return firestore.client()

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

    # Default to Senior if type is still unknown (most common case)
    if team_type == "Unknown":
        # Check if it's likely a senior competition
        if any(kw in comp_name_lower for kw in ['premier', 'pennant', 'vic league', 'metro']):
            team_type = "Senior"

    # Determine gender from competition name
    if "women's" in comp_name_lower:
        gender = "Women"
    elif "men's" in comp_name_lower:
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

def find_mentone_teams(competitions, db):
    """
    Scan round 1 of each competition to find Mentone teams and add to Firestore.

    Args:
        competitions (list): List of competition dictionaries
        db (firestore.Client): Firestore client
    """
    logger.info(f"Scanning {len(competitions)} competitions for Mentone teams...")
    seen = set()
    processed_count = 0
    club_name = "Mentone"  # Club variable for consistent naming

    # Create collections for Firestore
    competitions_collection = {}
    grades_collection = {}

    for comp in competitions:
        processed_count += 1
        comp_name = comp['name']
        round_url = f"https://www.hockeyvictoria.org.au/games/{comp['comp_id']}/{comp['fixture_id']}/round/1"

        logger.info(f"[{processed_count}/{len(competitions)}] Checking {comp_name} at {round_url}")

        response = make_request(round_url)
        if not response:
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        found_in_comp = False

        for a in soup.find_all("a"):
            text = a.text.strip()
            if TEAM_FILTER.lower() in text.lower() and is_valid_team(text):
                team_type, gender = classify_team(comp_name)
                team_name = create_team_name(comp_name)
                key = (team_name, comp['fixture_id'])

                if key in seen:
                    continue

                seen.add(key)

                # Add team to local storage
                team_data = {
                    "name": team_name,
                    "fixture_id": int(comp['fixture_id']),
                    "comp_id": int(comp['comp_id']),
                    "comp_name": comp['name'],
                    "type": team_type,
                    "gender": gender,
                    "club": club_name
                }
                mentone_teams.append(team_data)

                # Process competition for Firestore if it's new
                comp_id = int(comp['comp_id'])
                if comp_id not in competitions_collection:
                    comp_parts = comp['name'].split(" - ")
                    season = comp_parts[1] if len(comp_parts) > 1 else "2025"

                    # Create composite competition ID
                    composite_id = f"comp_{team_type.lower()}_{comp_id}"
                    competition_name = f"{season} {team_type} Competition"

                    competitions_collection[comp_id] = {
                        "id": composite_id,
                        "comp_id": comp_id,
                        "name": competition_name,
                        "type": team_type,
                        "season": season,
                        "start_date": "2025-03-15",  # Placeholder
                        "end_date": "2025-09-20",    # Placeholder
                        "rounds": 18                 # Placeholder
                    }

                # Process grade for Firestore if it's new
                fixture_id = int(comp['fixture_id'])
                if fixture_id not in grades_collection:
                    # Extract grade name from comp name
                    comp_parts = comp['name'].split(" - ")
                    grade_name = comp_parts[0]

                    # Create composite grade ID
                    composite_grade_id = f"grade_{team_type.lower()}_{fixture_id}"
                    competition_id = f"comp_{team_type.lower()}_{comp_id}"

                    grades_collection[fixture_id] = {
                        "id": composite_grade_id,
                        "fixture_id": fixture_id,
                        "comp_id": comp_id,
                        "name": grade_name,
                        "gender": gender,
                        "competition": competitions_collection[comp_id]["name"],
                        "competition_ref": db.collection("competitions").document(competition_id)
                    }

                found_in_comp = True
                logger.info(f"Found team: {team_name} ({team_type}, {gender})")

        if not found_in_comp:
            logger.debug(f"No Mentone teams found in {comp_name}")

    # Save competitions to Firestore
    for comp_id, comp_data in competitions_collection.items():
        db.collection("competitions").document(comp_data["id"]).set(comp_data)
        logger.info(f"Added competition to Firestore: {comp_data['name']} with ID {comp_data['id']}")

    # Save grades to Firestore
    for fixture_id, grade_data in grades_collection.items():
        db.collection("grades").document(grade_data["id"]).set(grade_data)
        logger.info(f"Added grade to Firestore: {grade_data['name']} with ID {grade_data['id']}")

    # Save teams to Firestore
    for team in mentone_teams:
        fixture_id = team["fixture_id"]
        comp_id = team["comp_id"]
        team_type = team["type"].lower()

        # Create composite IDs for references
        competition_id = f"comp_{team_type}_{comp_id}"
        grade_id = f"grade_{team_type}_{fixture_id}"
        team_id = f"team_{team_type}_{fixture_id}"

        team_data = {
            "id": team_id,
            "name": team["name"],
            "fixture_id": fixture_id,
            "comp_id": comp_id,
            "type": team["type"],
            "gender": team["gender"],
            "club": team["club"],
            "grade_ref": db.collection("grades").document(grade_id),
            "competition_ref": db.collection("competitions").document(competition_id)
        }

        db.collection("teams").document(team_id).set(team_data)
        logger.info(f"Added team to Firestore: {team['name']} with ID {team_id}")

    logger.info(f"Team discovery complete. Found {len(mentone_teams)} teams.")

def setup_settings(db):
    """Create settings collection in Firestore"""
    logger.info("Setting up settings collection...")

    settings_data = {
        "id": "email_settings",
        "pre_game_hours": 24,
        "weekly_summary_day": "Sunday",
        "weekly_summary_time": "20:00",
        "admin_emails": ["admin@mentone.com"]
    }

    db.collection("settings").document("email_settings").set(settings_data)
    logger.info("Added email settings to Firestore")

def main():
    """Main function to run the builder script and populate Firestore."""
    start_time = time.time()
    logger.info(f"=== Mentone Hockey Club Team Builder ===")
    logger.info(f"Starting team discovery process. Looking for teams containing '{TEAM_FILTER}'")

    try:
        # Initialize Firestore
        db = initialize_firebase()

        # Clear existing data (optional - uncomment if needed)
        collections = ["competitions", "grades", "teams"]
        for collection in collections:
            docs = db.collection(collection).stream()
            for doc in docs:
                doc.reference.delete()
            logger.info(f"Deleted all documents in {collection}")

        # Run the builder process
        comps = get_competition_blocks()
        if comps:
            find_mentone_teams(comps, db)
            setup_settings(db)
        else:
            logger.error("No competitions found. Exiting.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)

    elapsed_time = time.time() - start_time
    logger.info(f"Script completed in {elapsed_time:.2f} seconds")
    logger.info(f"Total competitions scanned: {len(comps) if 'comps' in locals() else 0}")
    logger.info(f"Total teams discovered: {len(mentone_teams)}")

if __name__ == "__main__":
    main()