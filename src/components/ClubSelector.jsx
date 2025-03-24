import React, { useState, useEffect } from 'react';
import { fetchAllClubs } from '../services/firestoreService';

const ClubSelector = ({ onSelectClub, currentClubId = null }) => {
    const [clubs, setClubs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');

    useEffect(() => {
        const loadClubs = async () => {
            try {
                setLoading(true);
                const clubsData = await fetchAllClubs();

                // Sort clubs (home club first, then alphabetically)
                clubsData.sort((a, b) => {
                    if (a.is_home_club && !b.is_home_club) return -1;
                    if (!a.is_home_club && b.is_home_club) return 1;
                    return a.name.localeCompare(b.name);
                });

                setClubs(clubsData);
            } catch (error) {
                console.error('Error loading clubs:', error);
            } finally {
                setLoading(false);
            }
        };

        loadClubs();
    }, []);

    // Filter clubs based on search term
    const filteredClubs = searchTerm
        ? clubs.filter(club =>
            club.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            club.short_name.toLowerCase().includes(searchTerm.toLowerCase())
        )
        : clubs;

    return (
        <div className="mb-6">
            <div className="mb-4">
                <label htmlFor="club-search" className="block text-sm font-medium text-gray-700 mb-1">
                    Search Clubs
                </label>
                <input
                    type="text"
                    id="club-search"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    placeholder="Search by club name..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                />
            </div>

            {loading ? (
                <div className="text-center py-4">
                    <p className="text-gray-500">Loading clubs...</p>
                </div>
            ) : (
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                    {filteredClubs.map(club => (
                        <div
                            key={club.id}
                            className={`
                border rounded-lg p-3 cursor-pointer transition-all
                ${currentClubId === club.id ? 'ring-2 ring-blue-500 bg-blue-50' : 'hover:bg-gray-50'}
              `}
                            onClick={() => onSelectClub(club)}
                            style={{
                                borderLeftWidth: '4px',
                                borderLeftColor: club.primary_color || '#333333'
                            }}
                        >
                            <div className="flex items-center">
                                {club.logo_url ? (
                                    <img
                                        src={club.logo_url}
                                        alt={club.name}
                                        className="w-8 h-8 mr-2"
                                    />
                                ) : (
                                    <div
                                        className="w-8 h-8 mr-2 rounded-full flex items-center justify-center text-white font-bold text-xs"
                                        style={{ backgroundColor: club.primary_color || '#333333' }}
                                    >
                                        {club.code || club.short_name.substring(0, 2).toUpperCase()}
                                    </div>
                                )}
                                <div>
                                    <h3 className="font-medium text-sm truncate" title={club.name}>
                                        {club.short_name}
                                    </h3>
                                    {club.is_home_club && (
                                        <span className="inline-block px-2 py-0.5 bg-blue-100 text-blue-800 text-xs rounded-full">
                      Home Club
                    </span>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))}

                    {filteredClubs.length === 0 && (
                        <div className="col-span-full text-center py-4">
                            <p className="text-gray-500">No clubs match your search</p>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default ClubSelector;