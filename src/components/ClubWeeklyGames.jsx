import React, { useState, useEffect } from 'react';
import WeeklyGames from './WeeklyGames';
import ClubVenues from './ClubVenues';
import TeamStats from './TeamStats';

const ClubWeeklyGames = ({ clubId = 'club_mentone' }) => {
    const [viewMode, setViewMode] = useState('weekly'); // 'weekly', 'teams', 'venues'
    const [teams, setTeams] = useState([]);
    const [selectedTeam, setSelectedTeam] = useState(null);
    const [loading, setLoading] = useState(false);

    // Fetch teams (mock data for now)
    useEffect(() => {
        setLoading(true);

        // Mock data - would be fetched from Firestore in production
        const mockTeams = [
            {
                id: 1,
                name: "Mentone - Women's Premier League",
                gender: "Women",
                type: "Senior",
                wins: 5,
                losses: 2,
                draws: 1
            },
            {
                id: 2,
                name: "Mentone - Women's Premier League Reserves",
                gender: "Women",
                type: "Senior",
                wins: 4,
                losses: 3,
                draws: 1
            },
            {
                id: 3,
                name: "Mentone - Men's Vic League 1",
                gender: "Men",
                type: "Senior",
                wins: 6,
                losses: 1,
                draws: 1
            },
            {
                id: 4,
                name: "Mentone - Men's Vic League 1 Reserves",
                gender: "Men",
                type: "Senior",
                wins: 3,
                losses: 3,
                draws: 2
            },
            {
                id: 5,
                name: "Mentone - Under 14 Mixed",
                gender: "Mixed",
                type: "Junior",
                wins: 3,
                losses: 1,
                draws: 0
            },
            {
                id: 6,
                name: "Mentone - Masters Men",
                gender: "Men",
                type: "Midweek",
                wins: 1,
                losses: 1,
                draws: 2
            }
        ];

        setTeams(mockTeams);
        setLoading(false);
    }, []);

    // Handle team selection
    const handleTeamSelect = (team) => {
        setSelectedTeam(team);
    };

    // Reset team selection
    const handleBackToTeams = () => {
        setSelectedTeam(null);
    };

    return (
        <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
            {/* Page header */}
            <div className="mb-6">
                <h1 className="text-3xl font-bold text-blue-800">Mentone Hockey Club</h1>
                <p className="text-gray-600">Fixtures and Results</p>
            </div>

            {/* Navigation tabs */}
            <div className="flex border-b mb-6">
                <button
                    className={`px-4 py-2 mr-2 font-medium ${
                        viewMode === 'weekly'
                            ? 'border-b-2 border-blue-500 text-blue-600'
                            : 'text-gray-500'
                    }`}
                    onClick={() => setViewMode('weekly')}
                >
                    Weekly Schedule
                </button>
                <button
                    className={`px-4 py-2 mr-2 font-medium ${
                        viewMode === 'teams'
                            ? 'border-b-2 border-blue-500 text-blue-600'
                            : 'text-gray-500'
                    }`}
                    onClick={() => setViewMode('teams')}
                >
                    Teams
                </button>
                <button
                    className={`px-4 py-2 mr-2 font-medium ${
                        viewMode === 'venues'
                            ? 'border-b-2 border-blue-500 text-blue-600'
                            : 'text-gray-500'
                    }`}
                    onClick={() => setViewMode('venues')}
                >
                    Venues
                </button>
            </div>

            {/* View content */}
            {viewMode === 'weekly' && <WeeklyGames clubId={clubId} />}

            {viewMode === 'teams' && (
                selectedTeam ? (
                    <div>
                        <div className="mb-4">
                            <button
                                onClick={handleBackToTeams}
                                className="flex items-center text-blue-600 hover:text-blue-800"
                            >
                                <span className="mr-1">←</span> Back to Teams
                            </button>
                        </div>
                        <TeamStats team={selectedTeam} />
                    </div>
                ) : (
                    <div className="bg-white rounded-lg shadow p-6">
                        <h2 className="text-2xl font-bold text-blue-800 mb-4">Teams</h2>

                        {loading ? (
                            <div className="text-center py-8">Loading teams...</div>
                        ) : (
                            <div>
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                                    <div>
                                        <h3 className="font-semibold mb-3 text-lg">Senior Teams</h3>
                                        <div className="space-y-2">
                                            {teams
                                                .filter(team => team.type === 'Senior')
                                                .map(team => (
                                                    <div
                                                        key={team.id}
                                                        className="p-3 bg-gray-50 rounded border border-gray-200 hover:bg-gray-100 cursor-pointer"
                                                        onClick={() => handleTeamSelect(team)}
                                                    >
                                                        <div className="flex justify-between items-center">
                                                            <span>{team.name}</span>
                                                            <span className="text-sm bg-gray-200 px-2 py-1 rounded">
                                {team.wins}W - {team.losses}L - {team.draws}D
                              </span>
                                                        </div>
                                                    </div>
                                                ))}
                                        </div>
                                    </div>

                                    <div>
                                        <h3 className="font-semibold mb-3 text-lg">Junior Teams</h3>
                                        <div className="space-y-2">
                                            {teams
                                                .filter(team => team.type === 'Junior')
                                                .map(team => (
                                                    <div
                                                        key={team.id}
                                                        className="p-3 bg-gray-50 rounded border border-gray-200 hover:bg-gray-100 cursor-pointer"
                                                        onClick={() => handleTeamSelect(team)}
                                                    >
                                                        <div className="flex justify-between items-center">
                                                            <span>{team.name}</span>
                                                            <span className="text-sm bg-gray-200 px-2 py-1 rounded">
                                {team.wins}W - {team.losses}L - {team.draws}D
                              </span>
                                                        </div>
                                                    </div>
                                                ))}
                                        </div>
                                    </div>

                                    <div>
                                        <h3 className="font-semibold mb-3 text-lg">Midweek Teams</h3>
                                        <div className="space-y-2">
                                            {teams
                                                .filter(team => team.type === 'Midweek')
                                                .map(team => (
                                                    <div
                                                        key={team.id}
                                                        className="p-3 bg-gray-50 rounded border border-gray-200 hover:bg-gray-100 cursor-pointer"
                                                        onClick={() => handleTeamSelect(team)}
                                                    >
                                                        <div className="flex justify-between items-center">
                                                            <span>{team.name}</span>
                                                            <span className="text-sm bg-gray-200 px-2 py-1 rounded">
                                {team.wins}W - {team.losses}L - {team.draws}D
                              </span>
                                                        </div>
                                                    </div>
                                                ))}
                                        </div>
                                    </div>
                                </div>

                                <div className="bg-blue-50 p-4 rounded border border-blue-100">
                                    <h3 className="font-semibold mb-2">Club Summary</h3>
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                        <div className="text-center">
                                            <p className="text-sm text-gray-500">Total Teams</p>
                                            <p className="text-xl font-bold">{teams.length}</p>
                                        </div>
                                        <div className="text-center">
                                            <p className="text-sm text-gray-500">Wins</p>
                                            <p className="text-xl font-bold">{teams.reduce((sum, team) => sum + team.wins, 0)}</p>
                                        </div>
                                        <div className="text-center">
                                            <p className="text-sm text-gray-500">Losses</p>
                                            <p className="text-xl font-bold">{teams.reduce((sum, team) => sum + team.losses, 0)}</p>
                                        </div>
                                        <div className="text-center">
                                            <p className="text-sm text-gray-500">Draws</p>
                                            <p className="text-xl font-bold">{teams.reduce((sum, team) => sum + team.draws, 0)}</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                )
            )}

            {viewMode === 'venues' && <ClubVenues clubId={clubId} />}
        </div>
    );
};

export default ClubWeeklyGames;