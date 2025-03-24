// src/services/firestoreService.js
import { db } from '../../firebase';
import {
    collection,
    getDocs,
    query,
    where,
    orderBy,
    limit,
    Timestamp,
    doc,
    getDoc
} from 'firebase/firestore';

// Fetch teams by type (Senior, Junior, Midweek)
export const fetchTeamsByType = async (type) => {
    try {
        const teamsRef = collection(db, 'teams');
        const teamsQuery = query(teamsRef, where('type', '==', type));
        const querySnapshot = await getDocs(teamsQuery);

        const teams = [];
        querySnapshot.forEach((doc) => {
            teams.push({
                id: doc.id,
                ...doc.data(),
            });
        });

        return teams;
    } catch (error) {
        console.error('Error fetching teams by type:', error);
        throw error;
    }
};

// Fetch all teams
export const fetchAllTeams = async () => {
    try {
        const teamsRef = collection(db, 'teams');
        const querySnapshot = await getDocs(teamsRef);

        const teams = [];
        querySnapshot.forEach((doc) => {
            teams.push({
                id: doc.id,
                ...doc.data(),
            });
        });

        return teams;
    } catch (error) {
        console.error('Error fetching all teams:', error);
        throw error;
    }
};

// Fetch games for a specific team
export const fetchGamesByTeamId = async (teamId) => {
    try {
        const gamesRef = collection(db, 'games');
        const teamRef = doc(db, 'teams', teamId);

        // Query games where this team is referenced
        const gamesQuery = query(gamesRef, where('team_ref', '==', teamRef), orderBy('date', 'desc'));
        const querySnapshot = await getDocs(gamesQuery);

        const games = [];
        querySnapshot.forEach((doc) => {
            const data = doc.data();

            // Convert Firestore Timestamp to Date object
            const gameDate = data.date instanceof Timestamp ? data.date.toDate() : new Date(data.date);

            // Normalize game data
            games.push({
                id: doc.id,
                ...data,
                date: gameDate,
                // Add any other transformations needed
            });
        });

        return games;
    } catch (error) {
        console.error('Error fetching games by team:', error);
        throw error;
    }
};

// Fetch upcoming games
export const fetchUpcomingGames = async (teamIds = null, limit = 10) => {
    try {
        const gamesRef = collection(db, 'games');
        let gamesQuery;

        const now = new Date();

        if (teamIds && teamIds.length > 0) {
            // Convert team IDs to team references
            const teamRefs = teamIds.map(id => doc(db, 'teams', id));
            gamesQuery = query(
                gamesRef,
                where('team_ref', 'in', teamRefs),
                where('date', '>=', now),
                orderBy('date', 'asc'),
                limit(limit)
            );
        } else {
            gamesQuery = query(
                gamesRef,
                where('date', '>=', now),
                orderBy('date', 'asc'),
                limit(limit)
            );
        }

        const querySnapshot = await getDocs(gamesQuery);

        const games = [];
        querySnapshot.forEach((doc) => {
            const data = doc.data();
            const gameDate = data.date instanceof Timestamp ? data.date.toDate() : new Date(data.date);

            games.push({
                id: doc.id,
                ...data,
                date: gameDate,
            });
        });

        return games;
    } catch (error) {
        console.error('Error fetching upcoming games:', error);
        throw error;
    }
};

// Fetch recent completed games
export const fetchRecentGames = async (teamIds = null, limit = 10) => {
    try {
        const gamesRef = collection(db, 'games');
        let gamesQuery;

        const now = new Date();

        if (teamIds && teamIds.length > 0) {
            // Convert team IDs to team references
            const teamRefs = teamIds.map(id => doc(db, 'teams', id));
            gamesQuery = query(
                gamesRef,
                where('team_ref', 'in', teamRefs),
                where('status', '==', 'completed'),
                orderBy('date', 'desc'),
                limit(limit)
            );
        } else {
            gamesQuery = query(
                gamesRef,
                where('status', '==', 'completed'),
                orderBy('date', 'desc'),
                limit(limit)
            );
        }

        const querySnapshot = await getDocs(gamesQuery);

        const games = [];
        querySnapshot.forEach((doc) => {
            const data = doc.data();
            const gameDate = data.date instanceof Timestamp ? data.date.toDate() : new Date(data.date);

            games.push({
                id: doc.id,
                ...data,
                date: gameDate,
            });
        });

        return games;
    } catch (error) {
        console.error('Error fetching recent games:', error);
        throw error;
    }
};

// Fetch all competitions
export const fetchCompetitions = async () => {
    try {
        const competitionsRef = collection(db, 'competitions');
        const querySnapshot = await getDocs(competitionsRef);

        const competitions = [];
        querySnapshot.forEach((doc) => {
            competitions.push({
                id: doc.id,
                ...doc.data(),
            });
        });

        return competitions;
    } catch (error) {
        console.error('Error fetching competitions:', error);
        throw error;
    }
};

// Fetch players for a team
export const fetchPlayersByTeamId = async (teamId) => {
    try {
        const playersRef = collection(db, 'players');
        const teamRef = doc(db, 'teams', teamId);

        // Query for players where this team is their primary team
        const playersQuery = query(playersRef, where('primary_team_ref', '==', teamRef));
        const querySnapshot = await getDocs(playersQuery);

        const players = [];
        querySnapshot.forEach((doc) => {
            players.push({
                id: doc.id,
                ...doc.data(),
            });
        });

        return players;
    } catch (error) {
        console.error('Error fetching players by team:', error);
        throw error;
    }
};

// Fetch team stats and calculate additional metrics
export const fetchTeamStats = async (teamId) => {
    try {
        const gamesRef = collection(db, 'games');
        const teamRef = doc(db, 'teams', teamId);

        // Get all completed games for this team
        const gamesQuery = query(
            gamesRef,
            where('team_ref', '==', teamRef),
            where('status', '==', 'completed')
        );

        const querySnapshot = await getDocs(gamesQuery);

        let wins = 0;
        let losses = 0;
        let draws = 0;
        let goalsFor = 0;
        let goalsAgainst = 0;

        querySnapshot.forEach((doc) => {
            const game = doc.data();
            const isHomeTeam = game.home_team.id === teamId;

            const teamScore = isHomeTeam ? game.home_team.score : game.away_team.score;
            const opponentScore = isHomeTeam ? game.away_team.score : game.home_team.score;

            // Add to goals tally
            goalsFor += teamScore || 0;
            goalsAgainst += opponentScore || 0;

            // Determine result
            if (teamScore > opponentScore) {
                wins++;
            } else if (teamScore < opponentScore) {
                losses++;
            } else {
                draws++;
            }
        });

        return {
            games_played: querySnapshot.size,
            wins,
            losses,
            draws,
            points: (wins * 3) + draws, // Standard hockey scoring
            goals_for: goalsFor,
            goals_against: goalsAgainst,
            goal_difference: goalsFor - goalsAgainst,
            win_percentage: querySnapshot.size > 0 ? (wins / querySnapshot.size) * 100 : 0
        };
    } catch (error) {
        console.error('Error fetching team stats:', error);
        throw error;
    }
};

// Fetch player stats for a specific competition
export const fetchTopScorers = async (competitionId, limit = 10) => {
    try {
        const playersRef = collection(db, 'players');
        const compRef = doc(db, 'competitions', `comp_${competitionId}`);

        // First get all players in this competition
        const playersQuery = query(
            playersRef,
            where('teams', 'array-contains', compRef.id),
            orderBy('stats.goals', 'desc'),
            limit(limit)
        );

        const querySnapshot = await getDocs(playersQuery);

        const players = [];
        querySnapshot.forEach((doc) => {
            const player = doc.data();
            players.push({
                id: doc.id,
                name: player.name,
                team: player.primary_team_ref ? player.primary_team_ref.id : 'Unknown',
                goals: player.stats?.goals || 0,
                appearances: player.stats?.appearances || 0
            });
        });

        return players;
    } catch (error) {
        console.error('Error fetching top scorers:', error);
        throw error;
    }
};

// Aggregate club-wide statistics
export const fetchClubStats = async () => {
    try {
        // Get all teams
        const teams = await fetchAllTeams();

        // Get all completed games
        const gamesRef = collection(db, 'games');
        const gamesQuery = query(gamesRef, where('status', '==', 'completed'));
        const gamesSnapshot = await getDocs(gamesQuery);

        // Calculate stats
        let totalGames = 0;
        let wins = 0;
        let losses = 0;
        let draws = 0;
        let goalsFor = 0;
        let goalsAgainst = 0;

        const teamIds = teams.map(team => team.id);

        gamesSnapshot.forEach((doc) => {
            const game = doc.data();

            // Check if Mentone is home or away
            const homeTeamId = game.home_team?.id;
            const awayTeamId = game.away_team?.id;

            const isHomeTeam = teamIds.includes(homeTeamId);
            const isAwayTeam = teamIds.includes(awayTeamId);

            // Only count games where Mentone is playing
            if (isHomeTeam || isAwayTeam) {
                totalGames++;

                const mentoneScore = isHomeTeam ? game.home_team.score : game.away_team.score;
                const opponentScore = isHomeTeam ? game.away_team.score : game.home_team.score;

                goalsFor += mentoneScore || 0;
                goalsAgainst += opponentScore || 0;

                // Determine result
                if (mentoneScore > opponentScore) {
                    wins++;
                } else if (mentoneScore < opponentScore) {
                    losses++;
                } else {
                    draws++;
                }
            }
        });

        return {
            teams_count: teams.length,
            total_games: totalGames,
            wins,
            losses,
            draws,
            win_percentage: totalGames > 0 ? (wins / totalGames) * 100 : 0,
            goals_for: goalsFor,
            goals_against: goalsAgainst,
            goal_difference: goalsFor - goalsAgainst
        };
    } catch (error) {
        console.error('Error fetching club stats:', error);
        throw error;
    }
};