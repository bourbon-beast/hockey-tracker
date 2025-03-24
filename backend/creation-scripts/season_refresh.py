import firebase_admin
from firebase_admin import credentials, firestore
import requests
from bs4 import BeautifulSoup
import re
import json
import logging
import time
from urllib.parse import urljoin
from datetime import datetime
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"season_refresh_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
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
    """
    if " - " in team_name:
        club_name = team_name.split(" - ")[0].strip()
    else:
        # Handle case where there's no delimiter
        club_name = team_name.split()[0]

    # Generate club_id - lowercase, underscores
    club_id = f"club_{club_name.lower().replace(' ', '_').replace('-', '_')}"

    return club_name, club_id

def get_or_create_club(club_name, club_id):
    """
    Get existing club or create if it doesn't exist.
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
        return club_ref, True

    # Update timestamp for existing club
    club_ref.update({"updated_at": firestore.SERVER_TIMESTAMP})
    return club_ref, False

def classify_team(comp_name):
    """
    Classify a team by type and gender based on competition name.
    """
    comp_name_lower = comp_name.lower()

    # Determine team type
    team_type = "Unknown"
    for keyword, value in TYPE_KEYWORDS.items():
        if keyword in comp_name_lower:
            team_type = value
            break

    # Special case handling
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
        # Fall back to keyword checking
        gender = "Unknown"
        for keyword, value in GENDER_MAP.items():
            if keyword in comp_name_lower:
                gender = value
                break

    return team_type, gender

def create_team_name(comp_name, club="Mentone"):
    """Create a team name from competition name."""
    name = comp_name.split(' - ')[0] if ' - ' in comp_name else comp_name
    return f"{club} - {name}"

def is_valid_team(name):
    """Filter out false positives like venue names."""
    invalid_keywords = ["playing fields", "grammar"]
    return all(kw not in name.lower() for kw in invalid_keywords) and "hockey club" in name.lower()

def get_competition_blocks():
    """Scrape the main page to get all competition blocks."""
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

    logger.info(f"Found {len(competitions)} competitions")
    return competitions

def get_or_create_competition(comp):
    """Get existing competition or create if new."""
    comp_id = int(comp["comp_id"])
    fixture_id = int(comp["fixture_id"])
    comp_name = comp["name"]

    comp_ref = db.collection("competitions").document(f"comp_{comp_id}")

    # Check if competition exists
    if not comp_ref.get().exists:
        # Determine competition type
        comp_type = "Senior"  # Default
        if "junior" in comp_name.lower() or any(f"u{i}" in comp_name.lower() for i in range(10, 19)):
            comp_type = "Junior"
        elif "masters" in comp_name.lower() or any(f"{i}+" in comp_name.lower() for i in [35, 45, 60]):
            comp_type = "Midweek/Masters"

        # Extract season info
        season = str(datetime.now().year)  # Default to current year
        if " - " in comp_name:
            parts = comp_name.split(" - ")
            if len(parts) > 1 and parts[1].strip().isdigit():
                season = parts[1].strip()

        # Create the Firestore document
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
    else:
        # Update existing competition
        comp_ref.update({
            "fixture_id": fixture_id,  # This might change between seasons
            "updated_at": firestore.SERVER_TIMESTAMP
        })
        logger.info(f"Updated competition: {comp_name} ({comp_id})")

    return comp_ref

def find_current_season_teams(competitions):
    """Find teams for the current season."""
    logger.info(f"Scanning {len(competitions)} competitions for current season teams...")
    mentone_teams = []
    team_ids_found = set()

    for comp in competitions:
        comp_name = comp['name']
        comp_id = int(comp['comp_id'])
        fixture_id = int(comp['fixture_id'])
        round_url = f"https://www.hockeyvictoria.org.au/games/{comp['comp_id']}/{comp['fixture_id']}/round/1"

        logger.info(f"Checking {comp_name} at {round_url}")

        # Get competition reference
        comp_ref = get_or_create_competition(comp)

        response = make_request(round_url)
        if not response:
            continue

        soup = BeautifulSoup(response.text, "html.parser")

        # Find Mentone teams
        for a in soup.find_all("a"):
            text = a.text.strip()
            if TEAM_FILTER.lower() in text.lower() and is_valid_team(text):
                # Extract club info
                club_name, club_id = extract_club_info(text)

                # Get or create club
                club_ref, _ = get_or_create_club(club_name, club_id)

                # Determine team type and gender
                team_type, gender = classify_team(comp_name)

                # Create team ID
                team_id = f"team_{fixture_id}_{club_id}"

                if team_id in team_ids_found:
                    continue

                team_ids_found.add(team_id)

                # Create team data
                team_data = {
                    "id": team_id,
                    "name": text,
                    "fixture_id": fixture_id,
                    "comp_id": comp_id,
                    "comp_name": comp_name,
                    "type": team_type,
                    "gender": gender,
                    "club": club_name,
                    "club_id": club_id,
                    "club_ref": club_ref,
                    "is_home_club": club_name.lower() == "mentone",
                    "season": datetime.now().year,
                    "created_at": firestore.SERVER_TIMESTAMP,
                    "updated_at": firestore.SERVER_TIMESTAMP,
                    "competition_ref": comp_ref,
                    "active": True
                }

                # Add to teams list
                mentone_teams.append(team_data)

                # Save to Firestore
                db.collection("teams").document(team_id).set(team_data)

                logger.info(f"Found Mentone team: {text} ({team_type}, {gender})")

    logger.info(f"Team discovery complete. Found {len(mentone_teams)} Mentone teams for current season.")
    return mentone_teams

def archive_old_teams():
    """Mark old teams as inactive."""
    current_year = datetime.now().year

    # Get all teams that don't have the current year as season
    teams_ref = db.collection("teams")
    teams_query = teams_ref.where("season", "<", current_year).stream()

    count = 0
    for team in teams_query:
        team.reference.update({
            "active": False,
            "updated_at": firestore.SERVER_TIMESTAMP
        })
        count += 1

    logger.info(f"Archived {count} teams from previous seasons")

def save_teams_to_json(teams, output_file=OUTPUT_FILE):
    """Save discovered teams to a JSON file."""
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
    """Main function to run the season refresh script."""
    start_time = time.time()
    logger.info(f"=== Mentone Hockey Club Season Refresh ===")
    logger.info(f"This will update teams for the current season while preserving existing data")

    try:
        # Archive old teams
        archive_old_teams()

        # Get competitions
        comps = get_competition_blocks()
        if not comps:
            logger.error("No competitions found. Exiting.")
            return

        # Find current season teams
        teams = find_current_season_teams(comps)

        # Save teams to JSON
        save_teams_to_json(teams)

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)

    elapsed_time = time.time() - start_time
    logger.info(f"Script completed in {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    main()