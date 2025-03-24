// src/App.jsx
import React, { useState, useEffect } from 'react';
import MentoneClubDashboard from './components/MentoneClubDashboard';
import TeamDetail from './components/TeamDetail';
import { fetchAllTeams } from './services/firestoreService';

function App() {
    const [teams, setTeams] = useState([]);
    const [selectedTeam, setSelectedTeam] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const loadTeams = async () => {
            try {
                setLoading(true);
                const teamsData = await fetchAllTeams();
                setTeams(teamsData);
            } catch (error) {
                console.error('Error loading teams:', error);
            } finally {
                setLoading(false);
            }
        };

        loadTeams();
    }, []);

    const handleTeamSelect = (team) => {
        setSelectedTeam(team);
    };

    const handleBackToDashboard = () => {
        setSelectedTeam(null);
    };

    return (
        <div className="min-h-screen bg-gray-100">
            <nav className="bg-blue-800 text-white p-4">
                <div className="max-w-7xl mx-auto">
                    <h1 className="text-2xl font-bold">Mentone Hockey Club</h1>
                </div>
            </nav>

            <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
                {loading ? (
                    <div className="flex justify-center py-20">
                        <p className="text-gray-500">Loading application data...</p>
                    </div>
                ) : selectedTeam ? (
                    <TeamDetail team={selectedTeam} onBack={handleBackToDashboard} />
                ) : (
                    <MentoneClubDashboard teams={teams} onTeamSelect={handleTeamSelect} />
                )}
            </main>

            <footer className="bg-gray-800 text-white p-4 mt-8">
                <div className="max-w-7xl mx-auto text-center text-sm">
                    <p>© {new Date().getFullYear()} Mentone Hockey Club</p>
                </div>
            </footer>
        </div>
    );
}

export default App;