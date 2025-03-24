import React, { useState, useEffect } from 'react';
import { db } from '../firebase.js';
import { collection, getDocs, query, where } from 'firebase/firestore';

function App() {
    const [teams, setTeams] = useState([]);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('Senior');

    useEffect(() => {
        async function fetchTeams() {
            try {
                setLoading(true);
                const teamsRef = collection(db, 'teams');
                const q = query(teamsRef, where('type', '==', activeTab));
                const querySnapshot = await getDocs(q);

                const teamsData = [];
                querySnapshot.forEach((doc) => {
                    teamsData.push(doc.data());
                });

                setTeams(teamsData);
            } catch (error) {
                console.error('Error fetching teams:', error);
            } finally {
                setLoading(false);
            }
        }

        fetchTeams();
    }, [activeTab]);

    const tabs = ['Senior', 'Junior', 'Midweek/Masters'];

    return (
        <div className="container mx-auto p-4">
            <header className="mb-6">
                <h1 className="text-3xl font-bold text-blue-800">Mentone Hockey Club</h1>
                <p className="text-gray-600">Team Fixture Tracker</p>
            </header>

            {/* Tabs */}
            <div className="flex border-b mb-6">
                {tabs.map((tab) => (
                    <button
                        key={tab}
                        className={`px-4 py-2 mr-2 font-medium ${
                            activeTab === tab
                                ? 'border-b-2 border-blue-500 text-blue-600'
                                : 'text-gray-500'
                        }`}
                        onClick={() => setActiveTab(tab)}
                    >
                        {tab}
                    </button>
                ))}
            </div>

            {/* Teams List */}
            {loading ? (
                <p>Loading teams...</p>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {teams.map((team) => (
                        <div
                            key={team.id}
                            className="border p-4 rounded shadow-sm"
                        >
                            <h2 className="text-lg font-semibold">{team.name}</h2>
                            <p>Gender: {team.gender}</p>
                            <p>Competition ID: {team.comp_id}</p>
                            <button className="mt-2 bg-blue-500 text-white px-3 py-1 rounded hover:bg-blue-600">
                                View Fixtures
                            </button>
                        </div>
                    ))}

                    {teams.length === 0 && (
                        <p className="col-span-full text-gray-500">No {activeTab} teams found</p>
                    )}
                </div>
            )}
        </div>
    );
}

export default App;