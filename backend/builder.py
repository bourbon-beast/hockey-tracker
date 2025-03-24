import requests
from bs4 import BeautifulSoup
import re
import json
import logging
import time
from urllib.parse import urljoin
from datetime import datetime

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

def find_mentone_teams(competitions):
    """
    Scan round 1 of each competition to find Mentone teams.

    Args:
        competitions (list): List of competition dictionaries
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
                key = (team_name, comp['fixture_id'])

                if key in seen:
                    continue

                seen.add(key)
                mentone_teams.append({
                    "name": team_name,
                    "fixture_id": int(comp['fixture_id']),
                    "comp_id": int(comp['comp_id']),
                    "comp_name": comp['name'],
                    "type": team_type,
                    "gender": gender,
                    "club": club_name
                })
                found_in_comp = True
                logger.info(f"Found team: {team_name} ({team_type}, {gender})")

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
        with open(output_file, "w") as f:
            json.dump(mentone_teams,
                      f, indent=2)
        logger.info(f"Successfully saved {len(mentone_teams)} teams to {output_file}")
    except Exception as e:
        logger.error(f"Failed to save teams to {output_file}: {e}")

def main():
    """Main function to run the builder script."""
    start_time = time.time()
    logger.info(f"=== Mentone Hockey Club Team Builder ===")
    logger.info(f"Starting team discovery process. Looking for teams containing '{TEAM_FILTER}'")

    try:
        comps = get_competition_blocks()
        if comps:
            find_mentone_teams(comps)
            save_teams_to_json()
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