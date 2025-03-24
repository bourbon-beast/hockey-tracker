import React, { useState, useEffect } from 'react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { fetchGamesByTeamId, fetchPlayersByTeamId, fetchTeamStats } from '../services/firestoreService';

const TeamDetail = ({ team, onBack }) => {
    const [games, setGames] = useState([]);
    const [players, setPlayers] = useState([]);
    const [teamStats, setTeamStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('fixtures');

    useEffect(() => {
        const loadTeamData = async () => {
            try {
                setLoading(true);

                // Fetch games, players and stats in parallel
                const [gamesData, playersData, statsData] = await Promise.all([
                    fetchGamesByTeamId(team.id),
                    fetchPlayersByTeamId(team.id),
                    fetchTeamStats(team.id)
                ]);

                setGames(gamesData);
                setPlayers(playersData);
                setTeamStats(statsData);
            } catch (error) {
                console.error('Error loading team data:', error);
            } finally {
                setLoading(false);
            }
        };

        loadTeamData();
    }, [team.id]);

    // Split games into upcoming and previous
    const upcomingGames = games.filter(game =>
        game.status === 'scheduled' && new Date(game.date) > new Date()
    ).sort((a, b) => new Date(a.date) - new Date(b.date));

    const completedGames = games.filter(game =>
        game.status === 'completed'
    ).sort((a, b) => new Date(b.date) - new Date(a.date));

    // Format date for display
    const formatDate = (dateStr) => {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-AU', {
            weekday: 'short',
            day: 'numeric',
            month: 'short',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    // Determine if a game result is a win, loss or draw
    const getGameResult = (game) => {
        const isHomeTeam = game.home_team.id === team.id;
        const teamScore = isHomeTeam ? game.home_team.score : game.away_team.score;
        const opponentScore = isHomeTeam ? game.away_team.score : game.home_team.score;

        if (teamScore > opponentScore) return 'win';
        if (teamScore < opponentScore) return 'loss';
        return 'draw';
    };

    // Create data for form chart
    const formData = completedGames.slice(0, 5).map(game => {
        const result = getGameResult(game);
        const isHomeTeam = game.home_team.id === team.id;
        const opponentName = isHomeTeam ? game.away_team.name : game.home_team.name;

        return {
            date: new Date(game.date).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' }),
            opponent: opponentName.replace('Mentone - ', ''),
            result: result === 'win' ? 3 : result === 'draw' ? 1 : 0,
            resultLabel: result.toUpperCase(),
            resultColor: result === 'win' ? '#4CAF50' : result === 'draw' ? '#FFC107' : '#F44336'
        };
    }).reverse();

    // Calculate stats
    const winPercentage = teamStats ? Math.round(teamStats.win_percentage) : 0;

    return (
        <div className="bg-white rounded-lg shadow p-6">
            {/* Header with team name and back button */}
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold text-blue-800">{team.name}</h2>
                <button
                    onClick={onBack}
                    className="px-3 py-1 bg-gray-200 hover:bg-gray-300 rounded"
                >
                    Back to Dashboard
                </button>
            </div>

            {loading ? (
                <div className="text-center py-8">Loading team details...</div>
            ) : (
                <>
                    {/* Stats cards */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                        <div className="bg-gray-50 p-3 rounded text-center">
                            <p className="text-sm text-gray-500">Games Played</p>
                            <p className="text-xl font-bold">{teamStats?.games_played || 0}</p>
                        </div>
                        <div className="bg-gray-50 p-3 rounded text-center">
                            <p className="text-sm text-gray-500">Record</p>
                            <p className="text-xl font-bold">
                                {teamStats?.wins || 0}W - {teamStats?.losses || 0}L - {teamStats?.draws || 0}D
                            </p>
                        </div>
                        <div className="bg-gray-50 p-3 rounded text-center">
                            <p className="text-sm text-gray-500">Win %</p>
                            <p className="text-xl font-bold">{winPercentage}%</p>
                        </div>
                        <div className="bg-gray-50 p-3 rounded text-center">
                            <p className="text-sm text-gray-500">Goal Diff</p>
                            <p className={`text-xl font-bold ${teamStats?.goal_difference > 0 ? 'text-green-600' : teamStats?.goal_difference < 0 ? 'text-red-600' : ''}`}>
                                {teamStats?.goal_difference > 0 ? '+' : ''}{teamStats?.goal_difference || 0}
                            </p>
                        </div>
                    </div>

                    {/* Tabs */}
                    <div className="border-b mb-6">
                        <div className="flex">
                            <button
                                className={`px-4 py-2 mr-2 font-medium ${activeTab === 'fixtures' ? 'border-b-2 border-blue-500 text-blue-600' : 'text-gray-500'}`}
                                onClick={() => setActiveTab('fixtures')}
                            >
                                Fixtures & Results
                            </button>
                            <button
                                className={`px-4 py-2 mr-2 font-medium ${activeTab === 'stats' ? 'border-b-2 border-blue-500 text-blue-600' : 'text-gray-500'}`}
                                onClick={() => setActiveTab('stats')}
                            >
                                Team Stats
                            </button>
                            <button
                                className={`px-4 py-2 mr-2 font-medium ${activeTab === 'players' ? 'border-b-2 border-blue-500 text-blue-600' : 'text-gray-500'}`}
                                onClick={() => setActiveTab('players')}
                            >
                                Players
                            </button>
                        </div>
                    </div>

                    {/* Tab content */}
                    {activeTab === 'fixtures' && (
                        <div>
                            {/* Form chart */}
                            {formData.length > 0 && (
                                <div className="mb-6">
                                    <h3 className="text-lg font-semibold mb-3">Recent Form</h3>
                                    <div className="flex justify-between items-center h-12">
                                        {formData.map((game, index) => (
                                            <div key={index} className="flex flex-col items-center">
                                                <div
                                                    className="w-10 h-10 rounded-full flex items-center justify-center text-white font-medium"
                                                    style={{ backgroundColor: game.resultColor }}
                                                >
                                                    {game.resultLabel[0]}
                                                </div>
                                                <span className="text-xs mt-1">{game.date}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Upcoming games */}
                            <div className="mb-6">
                                <h3 className="text-lg font-semibold mb-3">Upcoming Fixtures</h3>
                                {upcomingGames.length > 0 ? (
                                    <div className="bg-gray-50 rounded p-4">
                                        <ul className="divide-y">
                                            {upcomingGames.map(game => {
                                                const isHomeTeam = game.home_team.id === team.id;
                                                const opponentName = isHomeTeam
                                                    ? game.away_team.name
                                                    : game.home_team.name;

                                                return (
                                                    <li key={game.id} className="py-3">
                                                        <div className="text-sm text-gray-500">
                                                            {formatDate(game.date)} • {game.venue}
                                                        </div>
                                                        <div className="mt-1 flex items-center">
                                                            <span className="font-semibold mr-2">{isHomeTeam ? 'vs' : '@'}</span>
                                                            <span>{opponentName}</span>
                                                        </div>
                                                    </li>
                                                );
                                            })}
                                        </ul>
                                    </div>
                                ) : (
                                    <p className="text-gray-500 py-4 text-center">No upcoming fixtures</p>
                                )}
                            </div>

                            {/* Completed games */}
                            <div>
                                <h3 className="text-lg font-semibold mb-3">Results</h3>
                                {completedGames.length > 0 ? (
                                    <div className="overflow-x-auto">
                                        <table className="min-w-full divide-y divide-gray-200">
                                            <thead className="bg-gray-50">
                                            <tr>
                                                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                                                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Opponent</th>
                                                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Score</th>
                                                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Result</th>
                                                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Venue</th>
                                            </tr>
                                            </thead>
                                            <tbody className="bg-white divide-y divide-gray-200">
                                            {completedGames.map(game => {
                                                const isHomeTeam = game.home_team.id === team.id;
                                                const opponentName = isHomeTeam
                                                    ? game.away_team.name
                                                    : game.home_team.name;
                                                const result = getGameResult(game);
                                                const score = isHomeTeam
                                                    ? `${game.home_team.score} - ${game.away_team.score}`
                                                    : `${game.away_team.score} - ${game.home_team.score}`;

                                                return (
                                                    <tr key={game.id}>
                                                        <td className="px-4 py-2 whitespace-nowrap text-sm">
                                                            {new Date(game.date).toLocaleDateString()}
                                                        </td>
                                                        <td className="px-4 py-2 whitespace-nowrap text-sm">
                                                            {isHomeTeam ? 'vs ' : '@ '}{opponentName}
                                                        </td>
                                                        <td className="px-4 py-2 whitespace-nowrap text-sm font-medium">
                                                            {score}
                                                        </td>
                                                        <td className="px-4 py-2 whitespace-nowrap text-sm">
                                <span className={`px-2 py-1 rounded text-xs font-medium ${
                                    result === 'win' ? 'bg-green-100 text-green-800' :
                                        result === 'loss' ? 'bg-red-100 text-red-800' :
                                            'bg-yellow-100 text-yellow-800'
                                }`}>
                                  {result.toUpperCase()}
                                </span>
                                                        </td>
                                                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">
                                                            {game.venue}
                                                        </td>
                                                    </tr>
                                                );
                                            })}
                                            </tbody>
                                        </table>
                                    </div>
                                ) : (
                                    <p className="text-gray-500 py-4 text-center">No completed games</p>
                                )}
                            </div>
                        </div>
                    )}

                    {activeTab === 'stats' && (
                        <div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                {/* Goal Scoring */}
                                <div className="bg-gray-50 p-4 rounded">
                                    <h3 className="text-lg font-semibold mb-4">Goals</h3>
                                    <div className="h-64">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <BarChart
                                                data={completedGames.slice(0, 10).map(game => {
                                                    const isHomeTeam = game.home_team.id === team.id;
                                                    const opponentName = isHomeTeam
                                                        ? game.away_team.name.split(' - ').pop()
                                                        : game.home_team.name.split(' - ').pop();
                                                    const goalsFor = isHomeTeam
                                                        ? game.home_team.score
                                                        : game.away_team.score;
                                                    const goalsAgainst = isHomeTeam
                                                        ? game.away_team.score
                                                        : game.home_team.score;

                                                    return {
                                                        name: opponentName,
                                                        goalsFor: goalsFor || 0,
                                                        goalsAgainst: goalsAgainst || 0,
                                                        date: new Date(game.date).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' })
                                                    };
                                                }).reverse()}
                                                margin={{ top: 10, right: 30, left: 0, bottom: 40 }}
                                            >
                                                <CartesianGrid strokeDasharray="3 3" />
                                                <XAxis dataKey="date" angle={-45} textAnchor="end" height={50} />
                                                <YAxis />
                                                <Tooltip />
                                                <Legend />
                                                <Bar dataKey="goalsFor" fill="#4CAF50" name="Goals For" />
                                                <Bar dataKey="goalsAgainst" fill="#F44336" name="Goals Against" />
                                            </BarChart>
                                        </ResponsiveContainer>
                                    </div>
                                </div>

                                {/* Results Trend */}
                                <div className="bg-gray-50 p-4 rounded">
                                    <h3 className="text-lg font-semibold mb-4">Results Trend</h3>
                                    <div className="h-64">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <LineChart
                                                data={completedGames.slice(0, 10).map((game, index) => {
                                                    const result = getGameResult(game);
                                                    const pointsEarned = result === 'win' ? 3 : result === 'draw' ? 1 : 0;
                                                    const runningTotal = completedGames
                                                        .slice(0, index + 1)
                                                        .reduce((total, g) => {
                                                            const res = getGameResult(g);
                                                            return total + (res === 'win' ? 3 : res === 'draw' ? 1 : 0);
                                                        }, 0);

                                                    return {
                                                        name: new Date(game.date).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' }),
                                                        points: pointsEarned,
                                                        runningTotal: runningTotal
                                                    };
                                                }).reverse()}
                                                margin={{ top: 10, right: 30, left: 0, bottom: 40 }}
                                            >
                                                <CartesianGrid strokeDasharray="3 3" />
                                                <XAxis dataKey="name" angle={-45} textAnchor="end" height={50} />
                                                <YAxis />
                                                <Tooltip />
                                                <Legend />
                                                <Line type="monotone" dataKey="points" stroke="#8884d8" name="Points per Game" />
                                                <Line type="monotone" dataKey="runningTotal" stroke="#82ca9d" name="Cumulative Points" />
                                            </LineChart>
                                        </ResponsiveContainer>
                                    </div>
                                </div>
                            </div>

                            {/* Game Time Distribution */}
                            <div className="mt-6 bg-gray-50 p-4 rounded">
                                <h3 className="text-lg font-semibold mb-4">Game Time Distribution</h3>
                                <div className="h-64">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart
                                            data={[
                                                { time: 'Morning (7-12)', count: games.filter(g => {
                                                        const hour = new Date(g.date).getHours();
                                                        return hour >= 7 && hour < 12;
                                                    }).length },
                                                { time: 'Afternoon (12-5)', count: games.filter(g => {
                                                        const hour = new Date(g.date).getHours();
                                                        return hour >= 12 && hour < 17;
                                                    }).length },
                                                { time: 'Evening (5-9)', count: games.filter(g => {
                                                        const hour = new Date(g.date).getHours();
                                                        return hour >= 17 && hour < 21;
                                                    }).length },
                                                { time: 'Night (9+)', count: games.filter(g => {
                                                        const hour = new Date(g.date).getHours();
                                                        return hour >= 21;
                                                    }).length }
                                            ]}
                                            margin={{ top: 10, right: 30, left: 0, bottom: 40 }}
                                        >
                                            <CartesianGrid strokeDasharray="3 3" />
                                            <XAxis dataKey="time" />
                                            <YAxis />
                                            <Tooltip />
                                            <Legend />
                                            <Bar dataKey="count" fill="#8884d8" name="Number of Games" />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        </div>
                    )}

                    {activeTab === 'players' && (
                        <div>
                            {players.length > 0 ? (
                                <div className="overflow-x-auto">
                                    <table className="min-w-full divide-y divide-gray-200">
                                        <thead className="bg-gray-50">
                                        <tr>
                                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Player</th>
                                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Appearances</th>
                                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Goals</th>
                                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Cards</th>
                                        </tr>
                                        </thead>
                                        <tbody className="bg-white divide-y divide-gray-200">
                                        {players.map(player => (
                                            <tr key={player.id}>
                                                <td className="px-4 py-2 whitespace-nowrap text-sm font-medium">
                                                    {player.name}
                                                </td>
                                                <td className="px-4 py-2 whitespace-nowrap text-sm">
                                                    {player.stats?.appearances || 0}
                                                </td>
                                                <td className="px-4 py-2 whitespace-nowrap text-sm">
                                                    {player.stats?.goals || 0}
                                                </td>
                                                <td className="px-4 py-2 whitespace-nowrap text-sm">
                            <span className="inline-flex items-center">
                              <span className="inline-block w-3 h-3 bg-green-500 rounded-full mr-1"></span>
                                {player.stats?.green_cards || 0}
                            </span>
                                                    <span className="inline-flex items-center ml-2">
                              <span className="inline-block w-3 h-3 bg-yellow-500 rounded-full mr-1"></span>
                                                        {player.stats?.yellow_cards || 0}
                            </span>
                                                    <span className="inline-flex items-center ml-2">
                              <span className="inline-block w-3 h-3 bg-red-500 rounded-full mr-1"></span>
                                                        {player.stats?.red_cards || 0}
                            </span>
                                                </td>
                                            </tr>
                                        ))}
                                        </tbody>
                                    </table>
                                </div>
                            ) : (
                                <p className="text-gray-500 py-4 text-center">No player data available</p>
                            )}
                        </div>
                    )}
                </>
            )}
        </div>
    );
};

export default TeamDetail;