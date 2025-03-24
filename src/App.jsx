// src/App.jsx with Club Integration
import React, { useState, useEffect } from 'react';
import MentoneClubDashboard from './components/MentoneClubDashboard';
import TeamDetail from './components/TeamDetail';
import ClubDashboard from './components/ClubDashboard';
import ClubSelector from './components/ClubSelector';
import * as firestoreService from './services/firestoreService';

function App() {
    const [teams, setTeams] = useState([]);
    const [clubs, setClubs] = useState([]);
    const [selectedTeam, setSelectedTeam] = useState(null);
    const [selectedClub, setSelectedClub] = useState(null);
    const [viewMode, setViewMode] = useState('club'); // 'club', 'team', 'clubSelector'
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const loadInitialData = async () => {
            try {
                setLoading(true);

                // Load clubs and find the home club (Mentone)
                const clubsData = await firestoreService.fetchAllClubs();
                setClubs(clubsData);

                // Find the home club (Mentone)
                const homeClub = clubsData.find(club => club.is_home_club) ||
                    clubsData.find(club => club.name.includes('Mentone')) ||
                    (clubsData.length > 0 ? clubsData[0] : null);

                if (homeClub) {
                    setSelectedClub(homeClub);
                }

                // Load all teams
                const teamsData = await firestoreService.fetchAllTeams();
                setTeams(teamsData);
            } catch (error) {
                console.error('Error loading initial data:', error);
            } finally {
                setLoading(false);
            }
        };

        loadInitialData();
    }, []);

    const handleTeamSelect = (team) => {
        setSelectedTeam(team);
        setViewMode('team');
    };

    const handleClubSelect = (club) => {
        setSelectedClub(club);
        setViewMode('club');
    };

    const handleBackToDashboard = () => {
        setSelectedTeam(null);
        setViewMode('club');
    };

    const handleShowClubSelector = () => {
        setViewMode('clubSelector');
    };

    return (
        <div className="min-h-screen bg-gray-100">
            <nav className="bg-blue-800 text-white p-4">
                <div className="max-w-7xl mx-auto flex justify-between items-center">
                    <h1 className="text-2xl font-bold">
                        {selectedClub?.short_name || 'Mentone'} Hockey Club
                    </h1>
                    <div>
                        <button
                            onClick={handleShowClubSelector}
                            className="px-3 py-1 bg-blue-700 hover:bg-blue-600 rounded text-sm"
                        >
                            Change Club
                        </button>
                    </div>
                </div>
            </nav>

            <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
                {loading ? (
                    <div className="flex justify-center py-20">
                        <p className="text-gray-500">Loading application data...</p>
                    </div>
                ) : viewMode === 'team' && selectedTeam ? (
                    <TeamDetail team={selectedTeam} onBack={handleBackToDashboard} />
                ) : viewMode === 'clubSelector' ? (
                    <div className="bg-white rounded-lg shadow p-6">
                        <h2 className="text-xl font-bold mb-4">Select a Club</h2>
                        <ClubSelector
                            onSelectClub={handleClubSelect}
                            currentClubId={selectedClub?.id}
                        />
                    </div>
                ) : (
                    selectedClub ? (
                        <ClubDashboard
                            clubId={selectedClub.id}
                            firestoreService={firestoreService}
                            onTeamSelect={handleTeamSelect}
                        />
                    ) : (
                        <MentoneClubDashboard teams={teams} onTeamSelect={handleTeamSelect} />
                    )
                )}
            </main>

            <footer className="bg-gray-800 text-white p-4 mt-8">
                <div className="max-w-7xl mx-auto text-center text-sm">
                    <p>© {new Date().getFullYear()} Hockey Victoria Tracker</p>
                </div>
            </footer>
        </div>
    );
}

export default App;