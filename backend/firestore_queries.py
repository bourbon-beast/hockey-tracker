def get_teams_by_competition(comp_id):
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
        # Get grade data for each team
        grade_data = {}
        for team in teams:
            if 'grade_ref' in team:
                grade_doc = team['grade_ref'].get()
                if grade_doc.exists:
                    grade_data[team['id']] = grade_doc.to_dict()

        table_data = []
        for team in teams:
            grade_name = grade_data.get(team['id'], {}).get('name', 'Unknown')
            table_data.append([
                team['name'],
                grade_name,
                team['gender']
            ])

        headers = ["Team", "Grade", "Gender"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
    else:
        print(f"No teams found for competition {comp_id}")

    return teams

def get_teams_by_grade(fixture_id):
    """Get all teams in a specific grade (by fixture_id)"""
    print(f"Fetching teams for grade with fixture_id {fixture_id}...")

    teams_ref = db.collection("teams")
    query = teams_ref.where("fixture_id", "==", fixture_id)

    teams = []
    for doc in query.stream():
        team_data = doc.to_dict()
        teams.append(team_data)

    # Display as table
    if teams:
        table_data = []
        for team in teams:
            table_data.append([
                team['name'],
                team['gender'],
                team['club']
            ])

        headers = ["Team", "Gender", "Club"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
    else:
        print(f"No teams found for fixture_id {fixture_id}")

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

    # Group games by competition
    competitions = {}

    for game in games:
        comp_id = game.get('comp_id')
        if comp_id:
            comp_ref = db.collection("competitions").document(f"comp_{comp_id}")
            comp_doc = comp_ref.get()
            if comp_doc.exists:
                comp_data = comp_doc.to_dict()
                comp_name = comp_data.get('name', 'Unknown')

                if comp_name not in competitions:
                    competitions[comp_name] = []

                competitions[comp_name].append(game)

    # Print summary by competition
    for comp_name, comp_games in competitions.items():
        print(f"\n--- {comp_name} Summary ---")

        if comp_games:
            # Group by grade
            grades = {}
            for game in comp_games:
                grade_ref = game.get('grade_ref')
                if grade_ref:
                    grade_doc = grade_ref.get()
                    if grade_doc.exists:
                        grade_data = grade_doc.to_dict()
                        grade_name = grade_data.get('name', 'Unknown')

                        if grade_name not in grades:
                            grades[grade_name] = []

                        grades[grade_name].append(game)

            # Print each grade
            for grade_name, grade_games in grades.items():
                print(f"\n{grade_name}:")

                table_data = []
                for game in grade_games:
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
                        game['home_team']['name'],
                        f"{home_score} : {away_score}",
                        game['away_team']['name'],
                        result
                    ])

                headers = ["Date", "Home", "Score", "Away", "Result"]
                print(tabulate(table_data, headers=headers, tablefmt="grid"))
        else:
            print("No games played in this period")