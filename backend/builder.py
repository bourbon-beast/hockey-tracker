import requests
from bs4 import BeautifulSoup
import re
import json
import logging
import time
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
OUTPUT_FILE = "mentone_teams.json"
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

# Initialize Firebase (if needed)
def init_firebase():
    """Initialize Firebase if not already initialized."""
    if not firebase_admin._apps:
        try:
            cred = credentials.Certificate("../secrets/serviceAccountKey.json")
            firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized successfully")
        except Exception as e:
            logger.warning(f"Firebase initialization skipped: {e}")
            return None

    return firestore.client()

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

def create_or_get_club(db, club_name, club_id):
    """
    Create a club in Firestore if it doesn't exist.

    Args:
        db (firestore.Client): Firestore client
        club_name (str): Club name
        club_id (str): Generated club ID

    Returns:
        DocumentReference: Reference to the club document
    """
    if not db:
        logger.warning(f"Firebase not initialized, skipping club creation for {club_name}")
        return None

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

def find_mentone_teams(competitions, db=None):
    """
    Scan round 1 of each competition to find Mentone teams.

    Args:
        competitions (list): List of competition dictionaries
        db (firestore.Client): Firestore client for club creation
    """
    logger.info(f"Scanning {len(competitions)} competitions for Mentone teams...")
    seen = set()
    processed_count = 0
    club_name = "Mentone"  # Club variable for consistent naming

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

                # Extract club information
                club_name, club_id = extract_club_info(team_name)
                club_ref = None

                # Create or get club in Firestore if DB is available
                if db:
                    club_ref = create_or_get_club(db, club_name, club_id)

                key = (team_name, comp['fixture_id'])

                if key in seen:
                    continue

                seen.add(key)

                # Create team object
                team_data = {
                    "name": team_name,
                    "fixture_id": int(comp['fixture_id']),
                    "comp_id": int(comp['comp_id']),
                    "comp_name": comp['name'],
                    "type": team_type,
                    "gender": gender,
                    "club": club_name,
                    "club_id": club_id,
                    "is_home_club": club_name.lower() == "mentone"
                }

                # Add club reference if available
                if club_ref:
                    team_data["club_ref"] = club_ref

                mentone_teams.append(team_data)
                found_in_comp = True
                logger.info(f"Found team: {team_name} ({team_type}, {gender}, club: {club_name})")

        if not found_in_comp:
            logger.debug(f"No Mentone teams found in {comp_name}")

    logger.info(f"Team discovery complete. Found {len(mentone_teams)} teams.")

def save_teams_to_json(output_file=OUTPUT_FILE):
    """
    Save discovered teams to a JSON file.

    Args:
        output_file (str): Output file path
    """
    try:
        # Remove club_ref references as they're not JSON serializable
        cleaned_teams = []
        for team in mentone_teams:
            team_copy = team.copy()
            if 'club_ref' in team_copy:
                del team_copy['club_ref']
            cleaned_teams.append(team_copy)

        with open(output_file, "w") as f:
            json.dump(cleaned_teams, f, indent=2)
        logger.info(f"Successfully saved {len(mentone_teams)} teams to {output_file}")
    except Exception as e:
        logger.error(f"Failed to save teams to {output_file}: {e}")

def save_teams_to_firestore(db):
    """
    Save discovered teams to Firestore.

    Args:
        db (firestore.Client): Firestore client
    """
    if not db:
        logger.warning("Firebase not initialized, skipping Firestore save")
        return

    try:
        teams_collection = db.collection("teams")
        saved_count = 0

        for team in mentone_teams:
            team_id = f"team_{team['fixture_id']}"
            team_data = team.copy()

            # Add timestamps
            team_data["created_at"] = firestore.SERVER_TIMESTAMP
            team_data["updated_at"] = firestore.SERVER_TIMESTAMP

            # Save to Firestore
            teams_collection.document(team_id).set(team_data)
            saved_count += 1

        logger.info(f"Successfully saved {saved_count} teams to Firestore")
    except Exception as e:
        logger.error(f"Failed to save teams to Firestore: {e}")

def main():
    """Main function to run the builder script."""
    start_time = time.time()
    logger.info(f"=== Mentone Hockey Club Team Builder ===")
    logger.info(f"Starting team discovery process. Looking for teams containing '{TEAM_FILTER}'")

    try:
        # Initialize Firebase (optional)
        db = init_firebase()

        # Run the team discovery process
        comps = get_competition_blocks()
        if comps:
            find_mentone_teams(comps, db)
            save_teams_to_json()

            # Save to Firestore if available
            if db:
                save_teams_to_firestore(db)
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