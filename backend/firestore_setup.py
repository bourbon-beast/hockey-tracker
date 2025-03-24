import firebase_admin
from firebase_admin import credentials, firestore
import json
from datetime import datetime, timedelta
import os

# Initialize Firebase (you'll need to replace with your own credentials file)
if not firebase_admin._apps:
    cred = credentials.Certificate("path/to/serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

def setup_collections():
    """Set up all collections in Firestore based on mentone_teams.json"""
    # Load team data from JSON
    with open("backend/mentone_teams.json", "r") as f:
        teams_data = json.load(f)

    # Setup collections
    setup_competitions(teams_data)
    setup_teams(teams_data)
    setup_sample_games()
    setup_players()
    setup_settings()

    print("Firestore collections setup complete!")

def setup_competitions(teams_data):
    """Create competitions collection from team data"""
    print("Setting up competitions collection...")

    # Extract unique competitions from teams
    competitions = {}
    for team in teams_data:
        comp_id = team["comp_id"]

        if comp_id not in competitions:
            # Determine competition type based on name
            comp_type = "Senior"  # Default
            if "junior" in team["comp_name"].lower():
                comp_type = "Junior"
            elif any(keyword in team["comp_name"].lower() for keyword in ["masters", "midweek", "35+", "60+"]):
                comp_type = "Midweek/Masters"

            # Split out division from comp name
            comp_parts = team["comp_name"].split(" - ")
            division = comp_parts[0]
            season = comp_parts[1] if len(comp_parts) > 1 else "2025"

            competitions[comp_id] = {
                "id": f"comp_{comp_id}",
                "comp_id": comp_id,
                "name": team["comp_name"],
                "type": comp_type,
                "gender": team["gender"],
                "division": division,
                "season": season,
                "fixture_id": team["fixture_id"],
                "start_date": "2025-03-15",  # Placeholder
                "end_date": "2025-09-20",    # Placeholder
                "rounds": 18                 # Placeholder
            }

    # Add competitions to Firestore
    for comp_id, comp_data in competitions.items():
        db.collection("competitions").document(f"comp_{comp_id}").set(comp_data)
        print(f"Added competition: {comp_data['name']}")

def setup_teams(teams_data):
    """Create teams collection from team data"""
    print("Setting up teams collection...")

    for team in teams_data:
        team_id = f"team_{team['fixture_id']}"

        # Determine team type based on competition name
        team_type = "Senior"  # Default
        if "junior" in team["comp_name"].lower():
            team_type = "Junior"
        elif any(keyword in team["comp_name"].lower() for keyword in ["masters", "midweek", "35+", "60+"]):
            team_type = "Midweek/Masters"

        team_data = {
            "id": team_id,
            "name": team["name"],
            "fixture_id": team["fixture_id"],
            "comp_id": team["comp_id"],
            "type": team_type,
            "gender": team["gender"],
            "season": "2025",
            "club": team["club"],
            "competition_ref": db.collection("competitions").document(f"comp_{team['comp_id']}")
        }

        db.collection("teams").document(team_id).set(team_data)
        print(f"Added team: {team['name']}")

def setup_sample_games():
    """Create sample games for demonstration"""
    print("Setting up sample games collection...")

    # Get all teams
    teams_ref = db.collection("teams").stream()
    teams = {doc.id: doc.to_dict() for doc in teams_ref}

    # Create 3 sample games for each team
    game_count = 0
    for team_id, team in teams.items():
        for round_num in range(1, 4):
            # Create a game with this team as home team
            game_id = f"game_{team['fixture_id']}_{round_num}"

            # Generate a game date (Saturdays starting from April 5, 2025)
            game_date = datetime(2025, 4, 5) + timedelta(days=(round_num-1)*7)

            # Random opponent (just using the first team of opposite gender for demo)
            opponent_team = next(
                (t for t_id, t in teams.items() if t['gender'] != team['gender']),
                list(teams.values())[0]  # Fallback to first team
            )

            game_data = {
                "id": game_id,
                "fixture_id": team['fixture_id'],
                "round": round_num,
                "date": game_date,
                "venue": "Mentone Grammar Playing Fields",
                "home_team": {
                    "id": team_id,
                    "name": team['name'],
                    "score": round_num  # Placeholder score
                },
                "away_team": {
                    "id": opponent_team['id'],
                    "name": opponent_team['name'],
                    "score": round_num - 1  # Placeholder score
                },
                "status": "scheduled",
                "player_stats": {},
                "team_ref": db.collection("teams").document(team_id),
                "competition_ref": db.collection("competitions").document(f"comp_{team['comp_id']}")
            }

            db.collection("games").document(game_id).set(game_data)
            game_count += 1

    print(f"Added {game_count} sample games")

def setup_players():
    """Create sample players collection"""
    print("Setting up players collection...")

    # Get all teams
    teams_ref = db.collection("teams").stream()
    teams = {doc.id: doc.to_dict() for doc in teams_ref}

    # Sample player names
    mens_names = ["James Smith", "Michael Brown", "Robert Jones", "David Miller",
                  "John Wilson", "Thomas Moore", "Daniel Taylor", "Paul Anderson",
                  "Andrew Thomas", "Joshua White"]

    womens_names = ["Jennifer Smith", "Lisa Brown", "Mary Jones", "Sarah Miller",
                    "Jessica Wilson", "Emily Moore", "Emma Taylor", "Olivia Anderson",
                    "Isabella Thomas", "Sophia White"]

    # Create players for each team (5 players per team)
    player_count = 0
    for team_id, team in teams.items():
        # Choose names based on gender
        names = mens_names if team['gender'] == "Men" else womens_names

        for i in range(5):
            player_id = f"player_{team_id}_{i+1}"
            player_name = f"{names[i]} ({team['name'].split(' - ')[1]})"

            player_data = {
                "id": player_id,
                "name": player_name,
                "teams": [team_id],
                "stats": {
                    "goals": i*2,  # Sample stats
                    "green_cards": i % 3,
                    "yellow_cards": 0 if i < 4 else 1,
                    "red_cards": 0,
                    "appearances": 5
                },
                "gender": team['gender'],
                "primary_team_ref": db.collection("teams").document(team_id)
            }

            db.collection("players").document(player_id).set(player_data)
            player_count += 1

    print(f"Added {player_count} sample players")

def setup_settings():
    """Create settings collection"""
    print("Setting up settings collection...")

    settings_data = {
        "id": "email_settings",
        "pre_game_hours": 24,
        "weekly_summary_day": "Sunday",
        "weekly_summary_time": "20:00",
        "admin_emails": ["admin@mentone.com"]
    }

    db.collection("settings").document("email_settings").set(settings_data)
    print("Added email settings")

if __name__ == "__main__":
    setup_collections()