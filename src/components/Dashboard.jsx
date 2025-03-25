import React, { useState, useEffect } from 'react';
import ClubWeeklyGames from './ClubWeeklyGames';

const Dashboard = () => {
    const [club, setClub] = useState({
        id: 'club_mentone',
        name: 'Mentone Hockey Club',
        short_name: 'Mentone',
        primary_color: '#0066cc',
        is_home_club: true
    });
    const [isLoading, setIsLoading] = useState(false);

    // In a production app, you'd fetch the club information from Firestore
    // For this demo, we'll use the hard-coded values above

    return (
        <div className="min-h-screen bg-gray-100">
            {/* Navigation Header */}
            <nav className="bg-blue-800 text-white p-4">
                <div className="max-w-7xl mx-auto flex justify-between items-center">
                    <div className="flex items-center">
                        <div
                            className="w-10 h-10 rounded-full mr-3 flex items-center justify-center text-white font-bold"
                            style={{ backgroundColor: club.primary_color || '#0066cc' }}
                        >
                            {club.short_name?.substring(0, 1) || 'M'}
                        </div>
                        <h1 className="text-xl md:text-2xl font-bold hidden sm:block">
                            {club.name || 'Mentone Hockey Club'}
                        </h1>
                        <h1 className="text-xl md:text-2xl font-bold sm:hidden">
                            {club.short_name || 'Mentone'}
                        </h1>
                    </div>

                    <div className="flex space-x-2">
                        <button className="px-3 py-1 bg-blue-700 hover:bg-blue-600 rounded text-sm">
                            Account
                        </button>
                        <button className="px-3 py-1 bg-blue-700 hover:bg-blue-600 rounded text-sm">
                            Settings
                        </button>
                    </div>
                </div>
            </nav>

            {isLoading ? (
                <div className="flex justify-center items-center h-64">
                    <div className="text-gray-500">Loading...</div>
                </div>
            ) : (
                <main>
                    <div className="bg-white border-b shadow-sm">
                        <div className="max-w-7xl mx-auto py-3 px-4">
                            <div className="flex items-center text-sm">
                                <span className="text-blue-600">Dashboard</span>
                                <span className="mx-2 text-gray-400">/</span>
                                <span className="text-gray-500">{club.short_name}</span>
                            </div>
                        </div>
                    </div>

                    <ClubWeeklyGames clubId={club.id} />

                    <footer className="bg-gray-800 text-white p-4 mt-8">
                        <div className="max-w-7xl mx-auto text-center text-sm">
                            <p>© {new Date().getFullYear()} Hockey Tracker | Powered by Hockey Victoria</p>
                        </div>
                    </footer>
                </main>
            )}
        </div>
    );
};

export default Dashboard;