import React, { useState, useEffect } from 'react';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
    PieChart,
    Pie,
    Cell
} from 'recharts';

const TeamStats = ({ team }) => {
    const [stats, setStats] = useState({
        wins: 0,
        losses: 0,
        draws: 0,
        goalsFor: 0,
        goalsAgainst: 0,
        points: 0,
        winPercentage: 0,
        goalDifference: 0
    });

    const [recentResults, setRecentResults] = useState([]);
    const [loading, setLoading] = useState(true);

    // Colors for charts
    const COLORS = ['#22c55e', '#ef4444', '#f59e0b']; // green, red, amber

    useEffect(() => {
        // This would normally fetch data from Firestore
        // For demo purposes, we'll use sample data
        const calculateStats = () => {
            setLoading(true);

            // Sample data - in production, calculate this from actual games
            const teamStats = {
                wins: team.wins || 5,
                losses: team.losses || 2,
                draws: team.draws || 1,
                goalsFor: 18,
                goalsAgainst: 10,
                games: []
            };

            // Calculate derived stats
            teamStats.points = (teamStats.wins * 3) + teamStats.draws;
            teamStats.totalGames = teamStats.wins + teamStats.losses + teamStats.draws;
            teamStats.winPercentage = teamStats.totalGames > 0 ?
                Math.round((teamStats.wins / teamStats.totalGames) * 100) : 0;
            teamStats.goalDifference = teamStats.goalsFor - teamStats.goalsAgainst;

            // Create sample recent results
            const results = [
                { round: 8, opponent: 'Footscray', result: 'W', score: '3-1', date: '2025-03-20' },
                { round: 7, opponent: 'Hawthorn', result: 'D', score: '2-2', date: '2025-03-13' },
                { round: 6, opponent: 'RMIT', result: 'W', score: '2-0', date: '2025-03-06' },
                { round: 5, opponent: 'Melbourne', result: 'L', score: '1-2', date: '2025-02-28' },
                { round: 4, opponent: 'Doncaster', result: 'W', score: '4-1', date: '2025-02-20' }
            ];

            setStats(teamStats);
            setRecentResults(results);
            setLoading(false);
        };

        calculateStats();
    }, [team]);

    // Prepare data for charts
    const resultsData = [
        { name: 'Wins', value: stats.wins, color: '#22c55e' },
        { name: 'Losses', value: stats.losses, color: '#ef4444' },
        { name: 'Draws', value: stats.draws, color: '#f59e0b' }
    ];

    const goalsData = [
        { name: 'For', value: stats.goalsFor, color: '#3b82f6' },
        { name: 'Against', value: stats.goalsAgainst, color: '#6b7280' }
    ];

    // Custom tooltip for pie chart
    const renderCustomizedLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent, index, name, value }) => {
        const RADIAN = Math.PI / 180;
        const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
        const x = cx + radius * Math.cos(-midAngle * RADIAN);
        const y = cy + radius * Math.sin(-midAngle * RADIAN);

        return (
            <text
                x={x}
                y={y}
                fill="white"
                textAnchor={x > cx ? 'start' : 'end'}
                dominantBaseline="central"
            >
                {`${name}: ${value}`}
            </text>
        );
    };

    // Custom tooltip for bar chart
    const CustomTooltip = ({ active, payload, label }) => {
        if (active && payload && payload.length) {
            return (
                <div className="bg-white p-2 shadow border rounded">
                    <p className="font-medium">{`${label}: ${payload[0].value}`}</p>
                </div>
            );
        }
        return null;
    };

    if (loading) {
        return <div className="text-center py-8">Loading team statistics...</div>;
    }

    return (
        <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-2xl font-bold text-blue-800 mb-4">{team.name} Statistics</h2>

            {/* Stats Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div className="bg-gray-50 p-4 rounded text-center shadow-sm">
                    <p className="text-sm text-gray-500">Win Percentage</p>
                    <p className="text-2xl font-bold">{stats.winPercentage}%</p>
                </div>

                <div className="bg-gray-50 p-4 rounded text-center shadow-sm">
                    <p className="text-sm text-gray-500">Points</p>
                    <p className="text-2xl font-bold">{stats.points}</p>
                </div>

                <div className="bg-gray-50 p-4 rounded text-center shadow-sm">
                    <p className="text-sm text-gray-500">Goals For</p>
                    <p className="text-2xl font-bold">{stats.goalsFor}</p>
                </div>

                <div className="bg-gray-50 p-4 rounded text-center shadow-sm">
                    <p className="text-sm text-gray-500">Goal Difference</p>
                    <p className={`text-2xl font-bold ${stats.goalDifference > 0 ? 'text-green-600' : stats.goalDifference < 0 ? 'text-red-600' : ''}`}>
                        {stats.goalDifference > 0 ? '+' : ''}{stats.goalDifference}
                    </p>
                </div>
            </div>

            {/* Charts */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                {/* Results Pie Chart */}
                <div className="bg-gray-50 p-4 rounded">
                    <h3 className="text-lg font-semibold mb-3">Results Distribution</h3>
                    <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                                <Pie
                                    data={resultsData}
                                    cx="50%"
                                    cy="50%"
                                    labelLine={false}
                                    label={renderCustomizedLabel}
                                    outerRadius={80}
                                    fill="#8884d8"
                                    dataKey="value"
                                >
                                    {resultsData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.color} />
                                    ))}
                                </Pie>
                                <Tooltip />
                                <Legend />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Goals Bar Chart */}
                <div className="bg-gray-50 p-4 rounded">
                    <h3 className="text-lg font-semibold mb-3">Goals Comparison</h3>
                    <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart
                                data={goalsData}
                                margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
                            >
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis dataKey="name" />
                                <YAxis />
                                <Tooltip content={<CustomTooltip />} />
                                <Bar dataKey="value" name="Goals">
                                    {goalsData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.color} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>

            {/* Recent Results */}
            <div>
                <h3 className="text-lg font-semibold mb-3">Recent Results</h3>
                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                        <tr>
                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Round</th>
                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Opponent</th>
                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Result</th>
                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Score</th>
                        </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                        {recentResults.map((game, index) => (
                            <tr key={index}>
                                <td className="px-4 py-2 whitespace-nowrap text-sm font-medium">
                                    {game.round}
                                </td>
                                <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">
                                    {new Date(game.date).toLocaleDateString()}
                                </td>
                                <td className="px-4 py-2 whitespace-nowrap text-sm">
                                    {game.opponent}
                                </td>
                                <td className="px-4 py-2 whitespace-nowrap text-sm">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        game.result === 'W'
                            ? 'bg-green-100 text-green-800'
                            : game.result === 'L'
                                ? 'bg-red-100 text-red-800'
                                : 'bg-yellow-100 text-yellow-800'
                    }`}>
                      {game.result === 'W' ? 'Win' : game.result === 'L' ? 'Loss' : 'Draw'}
                    </span>
                                </td>
                                <td className="px-4 py-2 whitespace-nowrap text-sm font-medium">
                                    {game.score}
                                </td>
                            </tr>
                        ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

export default TeamStats;