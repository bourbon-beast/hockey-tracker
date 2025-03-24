import React, { useState, useEffect } from 'react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const MentoneClubDashboard = () => {
    // State management
    const [teams, setTeams] = useState([]);
    const [games, setGames] = useState([]);
    const [activeTab, setActiveTab] = useState('Senior');
    const [selectedTeam, setSelectedTeam] = useState(null);
    const [loading, setLoading] = useState(true);
    const [statsView, setStatsView] = useState('teams'); // 'teams', 'games', 'players'

    // Colors for charts
    const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8', '#82ca9d'];

    // Mock data loading - in production, this would fetch from Firestore
    useEffect(() => {
        // Simulating data fetch
        const mockTeams = [
            { id: 1, name: "Mentone - Women's Premier League", gender: "Women", type: "Senior", wins: 5, losses: 2, draws: 1 },
            { id: 2, name: "Mentone - Women's Premier League Reserves", gender: "Women", type: "Senior", wins: 4, losses: 3, draws: 1 },
            { id: 3, name: "Mentone - Men's Vic League 1", gender: "Men", type: "Senior", wins: 6, losses: 1, draws: 1 },
            { id: 4, name: "Mentone - Men's Vic League 1 Reserves", gender: "Men", type: "Senior", wins: 3, losses: 3, draws: 2 },
            { id: 5, name: "Mentone - Women's Pennant A", gender: "Women", type: "Senior", wins: 4, losses: 2, draws: 2 },
            { id: 6, name: "Mentone - Women's Pennant B", gender: "Women", type: "Senior", wins: 2, losses: 4, draws: 2 },
            { id: 7, name: "Mentone - Men's Pennant B", gender: "Men", type: "Senior", wins: 5, losses: 2, draws: 1 },
            { id: 8, name: "Mentone - Men's Pennant C", gender: "Men", type: "Senior", wins: 1, losses: 5, draws: 2 },
            { id: 9, name: "Mentone - Under 14 Mixed", gender: "Mixed", type: "Junior", wins: 3, losses: 1, draws: 0 },
            { id: 10, name: "Mentone - Under 16 Girls", gender: "Girls", type: "Junior", wins: 2, losses: 1, draws: 1 },
            { id: 11, name: "Mentone - Masters Men", gender: "Men", type: "Midweek", wins: 1, losses: 1, draws: 2 },
            { id: 12, name: "Mentone - Masters Women", gender: "Women", type: "Midweek", wins: 0, losses: 2, draws: 2 }
        ];

        const mockGames = [
            { id: 1, date: "2025-03-27", home: "Mentone - Women's Premier League", away: "Camberwell", homeScore: 3, awayScore: 1, status: "completed", venue: "Mentone Grammar Playing Fields", teamId: 1 },
            { id: 2, date: "2025-03-27", home: "Footscray", away: "Mentone - Men's Vic League 1", homeScore: 2, awayScore: 4, status: "completed", venue: "Footscray Hockey Centre", teamId: 3 },
            { id: 3, date: "2025-04-03", home: "Mentone - Women's Premier League", away: "Hawthorn", homeScore: null, awayScore: null, status: "scheduled", venue: "Mentone Grammar Playing Fields", teamId: 1 },
            { id: 4, date: "2025-04-03", home: "Mentone - Men's Vic League 1", away: "Essendon", homeScore: null, awayScore: null, status: "scheduled", venue: "Mentone Grammar Playing Fields", teamId: 3 },
            { id: 5, date: "2025-04-03", home: "Mentone - Under 14 Mixed", away: "Doncaster", homeScore: null, awayScore: null, status: "scheduled", venue: "Mentone Grammar Playing Fields", teamId: 9 },
            { id: 6, date: "2025-03-20", home: "Mentone - Men's Pennant B", away: "Melbourne", homeScore: 2, awayScore: 0, status: "completed", venue: "Mentone Grammar Playing Fields", teamId: 7 }
        ];

        setTeams(mockTeams);
        setGames(mockGames);
        setLoading(false);
    }, []);

    // Filter teams by active tab
    const filteredTeams = teams.filter(team => team.type === activeTab);

    // Filter games by active tab and selected team
    const filteredGames = selectedTeam
        ? games.filter(game => game.teamId === selectedTeam.id)
        : games.filter(game => {
            const teamIds = filteredTeams.map(team => team.id);
            return teamIds.includes(game.teamId);
        });

    // Separate upcoming games from past games
    const upcomingGames = filteredGames.filter(game => game.status === 'scheduled');
    const completedGames = filteredGames.filter(game => game.status === 'completed');

    // Calculate statistics
    const totalWins = filteredTeams.reduce((sum, team) => sum + team.wins, 0);
    const totalLosses = filteredTeams.reduce((sum, team) => sum + team.losses, 0);
    const totalDraws = filteredTeams.reduce((sum, team) => sum + team.draws, 0);

    // Data for gender distribution chart
    const genderData = [
        { name: 'Men', value: filteredTeams.filter(team => team.gender === 'Men').length },
        { name: 'Women', value: filteredTeams.filter(team => team.gender === 'Women').length },
        { name: 'Mixed', value: filteredTeams.filter(team => team.gender === 'Mixed').length }
    ].filter(item => item.value > 0);

    // Data for results pie chart
    const resultsData = [
        { name: 'Wins', value: totalWins },
        { name: 'Losses', value: totalLosses },
        { name: 'Draws', value: totalDraws }
    ];

    // Team performance chart data
    const performanceData = filteredTeams.map(team => ({
        name: team.name.split(' - ')[1], // Shortened name
        wins: team.wins,
        losses: team.losses,
        draws: team.draws
    }));

    return (
        <div className="max-w-7xl mx-auto p-4">
            {/* Header */}
            <header className="mb-6 flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold text-blue-800">Mentone Hockey Club</h1>
                    <p className="text-gray-600">Team Dashboard</p>
                </div>
                <div className="flex space-x-2">
                    <button
                        className={`px-3 py-1 rounded ${statsView === 'teams' ? 'bg-blue-600 text-white' : 'bg-gray-200'}`}
                        onClick={() => setStatsView('teams')}
                    >
                        Teams
                    </button>
                    <button
                        className={`px-3 py-1 rounded ${statsView === 'games' ? 'bg-blue-600 text-white' : 'bg-gray-200'}`}
                        onClick={() => setStatsView('games')}
                    >
                        Games
                    </button>
                    <button
                        className={`px-3 py-1 rounded ${statsView === 'players' ? 'bg-blue-600 text-white' : 'bg-gray-200'}`}
                        onClick={() => setStatsView('players')}
                    >
                        Players
                    </button>
                </div>
            </header>

            {/* Division Tabs */}
            <div className="flex border-b mb-6">
                {['Senior', 'Junior', 'Midweek'].map((tab) => (
                    <button
                        key={tab}
                        className={`px-4 py-2 mr-2 font-medium ${
                            activeTab === tab
                                ? 'border-b-2 border-blue-500 text-blue-600'
                                : 'text-gray-500'
                        }`}
                        onClick={() => {
                            setActiveTab(tab);
                            setSelectedTeam(null);
                        }}
                    >
                        {tab}
                    </button>
                ))}
            </div>

            {loading ? (
                <div className="flex justify-center py-20">
                    <p className="text-gray-500">Loading dashboard data...</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Left Column - Teams */}
                    <div className="lg:col-span-1">
                        <div className="bg-white rounded-lg shadow p-4 mb-6">
                            <h2 className="text-xl font-semibold mb-4">{activeTab} Teams</h2>
                            {filteredTeams.length > 0 ? (
                                <ul className="divide-y">
                                    {filteredTeams.map((team) => (
                                        <li
                                            key={team.id}
                                            className={`py-2 px-3 cursor-pointer hover:bg-gray-50 rounded ${
                                                selectedTeam?.id === team.id ? 'bg-blue-50 border-l-4 border-blue-500' : ''
                                            }`}
                                            onClick={() => setSelectedTeam(selectedTeam?.id === team.id ? null : team)}
                                        >
                                            <div className="flex justify-between items-center">
                                                <span>{team.name}</span>
                                                <span className="text-sm bg-gray-100 px-2 py-1 rounded">
                          {team.wins}W - {team.losses}L - {team.draws}D
                        </span>
                                            </div>
                                        </li>
                                    ))}
                                </ul>
                            ) : (
                                <p className="text-gray-500 py-4 text-center">No {activeTab} teams found</p>
                            )}
                        </div>

                        {/* Upcoming Fixtures */}
                        <div className="bg-white rounded-lg shadow p-4">
                            <h2 className="text-xl font-semibold mb-4">Upcoming Fixtures</h2>
                            {upcomingGames.length > 0 ? (
                                <ul className="divide-y">
                                    {upcomingGames.map((game) => (
                                        <li key={game.id} className="py-2">
                                            <div className="text-sm text-gray-500 mb-1">
                                                {new Date(game.date).toLocaleDateString()} • {game.venue}
                                            </div>
                                            <div className="flex justify-between font-medium">
                        <span>{game.home.includes('Mentone') ?
                            <span className="text-blue-600">{game.home.replace('Mentone - ', '')}</span> :
                            game.home}
                        </span>
                                                <span>vs</span>
                                                <span>{game.away.includes('Mentone') ?
                                                    <span className="text-blue-600">{game.away.replace('Mentone - ', '')}</span> :
                                                    game.away}
                        </span>
                                            </div>
                                        </li>
                                    ))}
                                </ul>
                            ) : (
                                <p className="text-gray-500 py-4 text-center">No upcoming games</p>
                            )}
                        </div>
                    </div>

                    {/* Center and Right Columns - Stats & Visualizations */}
                    <div className="lg:col-span-2">
                        {/* Key Stats */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                            <div className="bg-white rounded-lg shadow p-4 text-center">
                                <p className="text-gray-500 text-sm">Total Teams</p>
                                <p className="text-3xl font-bold text-blue-600">{filteredTeams.length}</p>
                            </div>
                            <div className="bg-white rounded-lg shadow p-4 text-center">
                                <p className="text-gray-500 text-sm">Win Percentage</p>
                                <p className="text-3xl font-bold text-green-600">
                                    {totalWins + totalLosses + totalDraws > 0
                                        ? Math.round((totalWins / (totalWins + totalLosses + totalDraws)) * 100)
                                        : 0}%
                                </p>
                            </div>
                            <div className="bg-white rounded-lg shadow p-4 text-center">
                                <p className="text-gray-500 text-sm">Upcoming Games</p>
                                <p className="text-3xl font-bold text-orange-500">{upcomingGames.length}</p>
                            </div>
                        </div>

                        {/* Charts based on view */}
                        {statsView === 'teams' && (
                            <>
                                {/* Team Performance */}
                                <div className="bg-white rounded-lg shadow p-4 mb-6">
                                    <h2 className="text-xl font-semibold mb-4">Team Performance</h2>
                                    <div className="h-72">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <BarChart
                                                data={performanceData}
                                                margin={{ top: 20, right: 30, left: 20, bottom: 60 }}
                                            >
                                                <CartesianGrid strokeDasharray="3 3" />
                                                <XAxis dataKey="name" angle={-45} textAnchor="end" height={70} />
                                                <YAxis />
                                                <Tooltip />
                                                <Legend />
                                                <Bar dataKey="wins" stackId="a" fill="#4CAF50" name="Wins" />
                                                <Bar dataKey="losses" stackId="a" fill="#F44336" name="Losses" />
                                                <Bar dataKey="draws" stackId="a" fill="#FFC107" name="Draws" />
                                            </BarChart>
                                        </ResponsiveContainer>
                                    </div>
                                </div>

                                {/* Split view for gender and results */}
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    {/* Gender Distribution */}
                                    <div className="bg-white rounded-lg shadow p-4">
                                        <h2 className="text-xl font-semibold mb-2">Gender Distribution</h2>
                                        <div className="h-60">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <PieChart>
                                                    <Pie
                                                        data={genderData}
                                                        cx="50%"
                                                        cy="50%"
                                                        innerRadius={60}
                                                        outerRadius={80}
                                                        fill="#8884d8"
                                                        paddingAngle={5}
                                                        dataKey="value"
                                                        label={({name, percent}) => `${name}: ${(percent * 100).toFixed(0)}%`}
                                                    >
                                                        {genderData.map((entry, index) => (
                                                            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                                        ))}
                                                    </Pie>
                                                    <Tooltip />
                                                </PieChart>
                                            </ResponsiveContainer>
                                        </div>
                                    </div>

                                    {/* Results Breakdown */}
                                    <div className="bg-white rounded-lg shadow p-4">
                                        <h2 className="text-xl font-semibold mb-2">Results Breakdown</h2>
                                        <div className="h-60">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <PieChart>
                                                    <Pie
                                                        data={resultsData}
                                                        cx="50%"
                                                        cy="50%"
                                                        innerRadius={60}
                                                        outerRadius={80}
                                                        fill="#8884d8"
                                                        paddingAngle={5}
                                                        dataKey="value"
                                                        label={({name, value}) => `${name}: ${value}`}
                                                    >
                                                        <Cell key="cell-0" fill="#4CAF50" /> {/* Wins */}
                                                        <Cell key="cell-1" fill="#F44336" /> {/* Losses */}
                                                        <Cell key="cell-2" fill="#FFC107" /> {/* Draws */}
                                                    </Pie>
                                                    <Tooltip />
                                                </PieChart>
                                            </ResponsiveContainer>
                                        </div>
                                    </div>
                                </div>
                            </>
                        )}

                        {statsView === 'games' && (
                            <>
                                {/* Recent Results */}
                                <div className="bg-white rounded-lg shadow p-4 mb-6">
                                    <h2 className="text-xl font-semibold mb-4">Recent Results</h2>
                                    {completedGames.length > 0 ? (
                                        <div className="overflow-x-auto">
                                            <table className="min-w-full divide-y divide-gray-200">
                                                <thead className="bg-gray-50">
                                                <tr>
                                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Teams</th>
                                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Score</th>
                                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Venue</th>
                                                </tr>
                                                </thead>
                                                <tbody className="bg-white divide-y divide-gray-200">
                                                {completedGames.map((game) => {
                                                    const isMentoneHome = game.home.includes('Mentone');
                                                    const isMentoneAway = game.away.includes('Mentone');
                                                    const mentoneWin = (isMentoneHome && game.homeScore > game.awayScore) ||
                                                        (isMentoneAway && game.awayScore > game.homeScore);
                                                    const mentoneLoss = (isMentoneHome && game.homeScore < game.awayScore) ||
                                                        (isMentoneAway && game.awayScore < game.homeScore);

                                                    return (
                                                        <tr key={game.id}>
                                                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                                                {new Date(game.date).toLocaleDateString()}
                                                            </td>
                                                            <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                                                                <div className={isMentoneHome ? "text-blue-600" : "text-gray-900"}>{game.home}</div>
                                                                <div className={isMentoneAway ? "text-blue-600" : "text-gray-900"}>{game.away}</div>
                                                            </td>
                                                            <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                                                                <div className={`${mentoneWin ? "text-green-600" : mentoneLoss ? "text-red-600" : "text-gray-600"} font-bold`}>
                                                                    {game.homeScore} - {game.awayScore}
                                                                </div>
                                                            </td>
                                                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
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
                            </>
                        )}

                        {statsView === 'players' && (
                            <div className="bg-white rounded-lg shadow p-4">
                                <h2 className="text-xl font-semibold mb-4">Player Statistics</h2>
                                <p className="text-gray-500 py-12 text-center">
                                    Player statistics will be available after data collection starts.
                                </p>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default MentoneClubDashboard;