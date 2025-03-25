import firebase_admin
from firebase_admin import credentials, firestore
import requests
from bs4 import BeautifulSoup
import logging
import time
import re
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"update_club_names_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
BASE_URL = "https://www.hockeyvictoria.org.au/games/team/"
REQUEST_TIMEOUT = 10  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# Initialize Firebase
cred = credentials.Certificate("../secrets/serviceAccountKey.json")
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

def extract_full_club_name(comp_id, team_id):
    """
    Scrape the full club name from a team page.

    Args:
        comp_id (str): Competition ID
        team_id (str): Team ID

    Returns:
        str or None: Full club name if found, None otherwise
    """
    url = f"{BASE_URL}{comp_id}/{team_id}"
    logger.info(f"Fetching club name from: {url}")

    response = make_request(url)
    if not response:
        logger.warning(f"Failed to fetch team page")
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    # Try to find the team heading which includes the club name
    # Format: "2025 Term 1 Summer Outdoor · KBH Brumbies Hockey Club"
    # Or: "2025 Senior Competition · Essendon Hockey"
    heading = soup.select_one("h2.h4")
    if heading:
        heading_text = heading.text.strip()
        logger.debug(f"Found heading: {heading_text}")

        # Check if it contains the club name after "·"
        if "·" in heading_text:
            club_part = heading_text.split("·")[1].strip()
            logger.info(f"Found full club name from heading: {club_part}")
            return club_part

    # If we can't find it that way, try other selectors
    team_links = soup.select("div.col-lg-3 a, .fixture-details-team-name")
    for link in team_links:
        href = link.get('href', '')
        if href and f"/games/team/{comp_id}" in href:
            full_name = link.text.strip()
            logger.info(f"Found full club name from team link: {full_name}")
            return full_name

    # Last attempt - try to find any mention of "Hockey Club" in the page
    club_patterns = [
        r'(\w+\s+(?:Hockey|HC))',
        r'(\w+\s+\w+\s+(?:Hockey|HC))',
        r'(\w+\s+\w+\s+\w+\s+(?:Hockey|HC))'
    ]

    page_text = soup.get_text()
    for pattern in club_patterns:
        matches = re.findall(pattern, page_text)
        if matches:
            logger.info(f"Found potential club name using pattern: {matches[0]}")
            return matches[0]

    logger.warning(f"Could not find full club name on page")
    return None

def update_club_names():
    """
    Update all club names in Firestore.
    """
    # Get all teams to collect comp_id and team_id pairs
    teams_ref = db.collection("teams").stream()
    teams = []

    for doc in teams_ref:
        team_data = doc.to_dict()
        teams.append({
            'id': doc.id,
            'name': team_data.get('name', ''),
            'comp_id': team_data.get('comp_id', ''),
            'club': team_data.get('club', ''),
            'club_id': team_data.get('club_id', '')
        })

    logger.info(f"Found {len(teams)} teams in Firestore")

    # Collect all unique clubs
    clubs = {}
    for team in teams:
        if 'club_id' in team and team['club_id'] not in clubs:
            clubs[team['club_id']] = {
                'current_name': team.get('club', ''),
                'full_name': None,
                'teams': []
            }

        if 'club_id' in team and team['club_id'] in clubs:
            clubs[team['club_id']]['teams'].append({
                'id': team['id'],
                'comp_id': team['comp_id']
            })

    logger.info(f"Found {len(clubs)} unique clubs")

    # For each club, try to scrape the full name
    for club_id, club_data in clubs.items():
        logger.info(f"Processing club: {club_data['current_name']} ({club_id})")

        # Try each team until we get a full name
        for team in club_data['teams']:
            # Normalize team ID if it contains prefix/suffix
            raw_team_id = team['id']
            if '_' in raw_team_id:
                raw_team_id = raw_team_id.split('_')[-1]

            full_club_name = extract_full_club_name(team['comp_id'], raw_team_id)

            if full_club_name:
                club_data['full_name'] = full_club_name
                # Once we find it, no need to check other teams
                break

            # Be nice to the server
            time.sleep(0.5)

        # If we didn't find a full name, keep the current one
        if not club_data['full_name']:
            club_data['full_name'] = club_data['current_name']
            logger.warning(f"Could not find full name for {club_data['current_name']}, keeping current name")
            continue

        # Update the club in Firestore
        logger.info(f"Updating club: {club_data['current_name']} -> {club_data['full_name']}")
        club_ref = db.collection("clubs").document(club_id)
        club_ref.update({
            'name': club_data['full_name'],
            'updated_at': firestore.SERVER_TIMESTAMP
        })

        # Also update club name in all teams
        for team in club_data['teams']:
            team_ref = db.collection("teams").document(team['id'])
            team_ref.update({
                'club': club_data['full_name'],
                'updated_at': firestore.SERVER_TIMESTAMP
            })

    logger.info("Club name update completed")

def display_club_changes():
    """
    Display all clubs before and after the update.
    """
    clubs_ref = db.collection("clubs").stream()
    logger.info("\nClub name changes:")
    logger.info("-" * 80)
    logger.info(f"{'Club ID':<20} | {'Original Name':<30} | {'Updated Name':<40}")
    logger.info("-" * 80)

    for doc in clubs_ref:
        club_data = doc.to_dict()
        logger.info(f"{doc.id:<20} | {club_data.get('short_name', ''):<30} | {club_data.get('name', ''):<40}")

def main():
    """
    Main function to update club names.
    """
    start_time = time.time()
    logger.info("=== Update Club Names Script ===")

    # Set debug level to DEBUG to see more information
    logger.setLevel(logging.DEBUG)

    try:
        # Update club names
        update_club_names()

        # Display changes
        display_club_changes()

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)

    elapsed_time = time.time() - start_time
    logger.info(f"Script completed in {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    main()