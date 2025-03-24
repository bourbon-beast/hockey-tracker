import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
import json
from tabulate import tabulate

# Initialize Firebase (if not already initialized)
if not firebase_admin._apps:
    cred = credentials.Certificate("path/to/serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

def get_upcoming_games(days=7):
    """Get all upcoming games in the next X days"""
    print(f"Fetching upcoming games in the next {days} days...")

    # Calculate date range
    start_date = datetime.now()
    end_date = start_date + timedelta(days=days)

    # Query games within date range
    games_ref = db.collection("games")
    query = games_ref.where("date", ">=", start_date).where("date", "<=", end_date)

    games = []
    for doc in query.stream():
        game_data = doc.to_dict()
        games.append(game_data)

    # Display as table
    if games:
        table_data = []
        for game in games:
            table_data.append([
                game['date'].strftime("%a %d %b %H:%M"),
                game['home_team']['name'].split(' - ')[1],
                f"{game['home_team'].get('score', '-')} : {game['away_team'].get('score', '-')}",
                game['away_team']['name'].split(' - ')[1],
                game['venue'],
                f"Round {game['round']}"
            ])

        headers = ["Date/Time", "Home", "Score", "Away", "Venue", "Round"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
    else:
        print("No upcoming games found")

    return games

def get_teams_by_type(team_type):
    """Get all teams by type (Senior, Junior, Midweek/Masters)"""
    print(f"Fetching all {team_type} teams...")

    teams_ref = db.collection("teams")
    query = teams_ref.where("type", "==", team_type)

    teams = []
    for doc in query.stream():
        team_data = doc.to_dict()
        teams.append(team_data)

    # Display as table
    if teams:
        table_data = []
        for team in teams:
            table_data.append([
                team['name'].split(' - ')[1],
                team['gender'],
                team.get('season', '2025')
            ])

        headers = ["Team", "Gender", "Season"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
    else:
        print(f"No {team_type} teams found")

    return teams

def get_player_stats(min_goals=0):
    """Get player stats for all players with at least X goals"""
    print(f"Fetching players with at least {min_goals} goals...")

    players_ref = db.collection("players")
    query = players_ref.where("stats.goals", ">=", min_goals)

    players = []
    for doc in query.stream():
        player_data = doc.to_dict()
        players.append(player_data)

    # Sort by goals (descending)
    players.sort(key=lambda x: x['stats']['goals'], reverse=True)

    # Display as table
    if players:
        table_data = []
        for player in players:
            table_data.append([
                player['name'],
                player['stats']['goals'],
                player['stats']['appearances'],
                player['stats']['green_cards'],
                player['stats']['yellow_cards'],
                player['stats']['red_cards'],
                player['gender']
            ])

        headers = ["Player", "Goals", "Games", "Green", "Yellow", "Red", "Gender"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
    else:
        print(f"No players found with at least {min_goals} goals")

    return players

def get_team_games(team_id):
    """Get all games for a specific team"""
    print(f"Fetching games for team {team_id}...")

    games_ref = db.collection("games")

    # Query for games where this team is either home or away
    # Note: This is a simplification. In a real app, you might need a more complex query
    # or use array membership if you stored both teams in an array
    query = games_ref.where("home_team.id", "==", team_id)

    games = []
    for doc in query.stream():
        game_data = doc.to_dict()
        games.append(game_data)

    # Query for away games
    query_away = games_ref.where("away_team.id", "==", team_id)
    for doc in query_away.stream():
        game_data = doc.to_dict()
        games.append(game_data)

    # Sort by date
    games.sort(key=lambda x: x['date'])

    # Display as table
    if games:
        table_data = []
        for game in games:
            table_data.append([
                game['date'].strftime("%a %d %b %H:%M"),
                game['home_team']['name'].split(' - ')[1],
                f"{game['home_team'].get('score', '-')} : {game['away_team'].get('score', '-')}",
                game['away_team']['name'].split(' - ')[1],
                game['venue'],
                f"Round {game['round']}"
            ])

        headers = ["Date/Time", "Home", "Score", "Away", "Venue", "Round"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
    else:
        print(f"No games found for team {team_id}")

    return games

def get_competition_teams(comp_id):
    """Get all teams in a specific competition"""
    print(f"Fetching teams for competition {comp_id}...")

    teams_ref = db.collection("teams")
    query = teams_ref.where("comp_id", "==", comp_id)

    teams = []
    for doc in query.stream():
        team_data = doc.to_dict()
        teams.append(team_data)

    # Display as table
    if teams:
        table_data = []
        for team in teams:
            table_data.append([
                team['name'].split(' - ')[1],
                team['gender'],
                team['type']
            ])

        headers = ["Team", "Gender", "Type"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
    else:
        print(f"No teams found for competition {comp_id}")

    return teams

def generate_weekly_summary():
    """Generate a weekly summary of games and results"""
    print("Generating weekly summary...")

    # Get games from the last 7 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    games_ref = db.collection("games")
    query = games_ref.where("date", ">=", start_date).where("date", "<=", end_date)

    games = []
    for doc in query.stream():
        game_data = doc.to_dict()
        games.append(game_data)

    # Group games by type (Senior, Junior, Midweek)
    game_types = {}

    for game in games:
        # Fetch the team to get its type
        team_ref = game.get('team_ref')
        if team_ref:
            team_data = team_ref.get().to_dict()
            team_type = team_data.get('type', 'Unknown')

            if team_type not in game_types:
                game_types[team_type] = []

            game_types[team_type].append(game)

    # Print summary by type
    for team_type, type_games in game_types.items():
        print(f"\n--- {team_type} Games Summary ---")

        if type_games:
            table_data = []
            for game in type_games:
                home_score = game['home_team'].get('score', '-')
                away_score = game['away_team'].get('score', '-')

                # Determine result from Mentone perspective
                home_is_mentone = "Mentone" in game['home_team']['name']
                if home_is_mentone:
                    if home_score > away_score:
                        result = "WIN"
                    elif home_score < away_score:
                        result = "LOSS"
                    else:
                        result = "DRAW"
                else:
                    if away_score > home_score:
                        result = "WIN"
                    elif away_score < home_score:
                        result = "LOSS"
                    else:
                        result = "DRAW"

                table_data.append([
                    game['date'].strftime("%a %d %b"),
                    game['home_team']['name'].split(' - ')[1],
                    f"{home_score} : {away_score}",
                    game['away_team']['name'].split(' - ')[1],
                    result
                ])

            headers = ["Date", "Home", "Score", "Away", "Result"]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
        else:
            print("No games played in this period")

# Example usage
if __name__ == "__main__":
    print("\n=== MENTONE HOCKEY CLUB DATA QUERIES ===\n")

    # Example queries
    get_upcoming_games()
    print("\n")

    get_teams_by_type("Senior")
    print("\n")

    get_player_stats(2)  # Players with at least 2 goals
    print("\n")

    # Note: You would replace this with an actual team ID from your database
    get_team_games("team_37291")  # Men's Vic League 1
    print("\n")

    # Generate weekly summary
    generate_weekly_summary()