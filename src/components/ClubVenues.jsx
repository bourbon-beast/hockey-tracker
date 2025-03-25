import React, { useState, useEffect } from 'react';
import VenueMap from './VenueMap';
import { fetchGamesByDateRange } from '../services/firestoreService';
import { format, startOfMonth, endOfMonth, addMonths, subMonths } from 'date-fns';

const ClubVenues = ({ clubId = 'club_mentone' }) => {
    const [venues, setVenues] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedVenue, setSelectedVenue] = useState(null);
    const [currentMonth, setCurrentMonth] = useState(() => startOfMonth(new Date()));
    const currentMonthEnd = endOfMonth(currentMonth);

    // Fetch games and extract venues
    useEffect(() => {
        const fetchVenueData = async () => {
            setLoading(true);

            try {
                // Get games for the selected month
                const gamesData = await fetchGamesByDateRange(
                    currentMonth,
                    currentMonthEnd,
                    clubId
                );

                // Extract unique venues with game counts
                const venueMap = new Map();

                gamesData.forEach(game => {
                    const venueName = game.venue || 'Unknown Venue';

                    if (!venueMap.has(venueName)) {
                        venueMap.set(venueName, {
                            id: venueName.replace(/\s+/g, '-').toLowerCase(),
                            name: venueName,
                            address: venueName, // Ideally would have real addresses
                            gamesCount: 1,
                            games: [game]
                        });
                    } else {
                        const venue = venueMap.get(venueName);
                        venue.gamesCount++;
                        venue.games.push(game);
                    }
                });

                // Convert to array and sort by game count
                const venuesData = Array.from(venueMap.values())
                    .sort((a, b) => b.gamesCount - a.gamesCount);

                setVenues(venuesData);
            } catch (error) {
                console.error('Error fetching venue data:', error);
            } finally {
                setLoading(false);
            }
        };

        fetchVenueData();
    }, [clubId, currentMonth, currentMonthEnd]);

    // Navigate to previous month
    const goToPreviousMonth = () => {
        setCurrentMonth(prev => subMonths(prev, 1));
    };

    // Navigate to next month
    const goToNextMonth = () => {
        setCurrentMonth(prev => addMonths(prev, 1));
    };

    // Navigate to current month
    const goToCurrentMonth = () => {
        setCurrentMonth(startOfMonth(new Date()));
    };

    // Handle venue selection
    const handleVenueSelect = (venue) => {
        setSelectedVenue(venue);
    };

    // Format date for display
    const formatGameDate = (date) => {
        return format(new Date(date), 'EEE, MMM d • h:mm a');
    };

    // Format month for display
    const formattedMonth = format(currentMonth, 'MMMM yyyy');

    return (
        <div className="bg-white rounded-lg shadow">
            <div className="p-6 border-b">
                <div className="flex justify-between items-center mb-4">
                    <h2 className="text-2xl font-bold text-blue-800">Venues</h2>

                    <div className="flex items-center space-x-2">
                        <button
                            onClick={goToPreviousMonth}
                            className="px-3 py-1 bg-gray-200 hover:bg-gray-300 rounded"
                        >
                            Previous
                        </button>

                        <button
                            onClick={goToCurrentMonth}
                            className="px-3 py-1 bg-blue-600 text-white hover:bg-blue-700 rounded"
                        >
                            Current Month
                        </button>

                        <button
                            onClick={goToNextMonth}
                            className="px-3 py-1 bg-gray-200 hover:bg-gray-300 rounded"
                        >
                            Next
                        </button>
                    </div>
                </div>

                <div className="text-lg font-medium text-center mb-4">{formattedMonth}</div>

                {loading ? (
                    <div className="text-center py-8">Loading venue data...</div>
                ) : venues.length === 0 ? (
                    <div className="text-center py-8 text-gray-500">
                        No games scheduled for this month
                    </div>
                ) : (
                    <VenueMap />
                )}
            </div>

            <div className="p-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <h3 className="text-lg font-semibold mb-3">All Venues ({venues.length})</h3>
                        <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
                            {venues.map(venue => (
                                <div
                                    key={venue.id}
                                    className={`p-3 rounded cursor-pointer border ${
                                        selectedVenue?.id === venue.id
                                            ? 'border-blue-500 bg-blue-50'
                                            : 'border-gray-200 hover:bg-gray-50'
                                    }`}
                                    onClick={() => handleVenueSelect(venue)}
                                >
                                    <div className="flex justify-between">
                                        <h4 className="font-medium">{venue.name}</h4>
                                        <span className="bg-blue-100 text-blue-800 text-xs font-semibold px-2 py-1 rounded-full">
                      {venue.gamesCount} {venue.gamesCount === 1 ? 'game' : 'games'}
                    </span>
                                    </div>
                                    <p className="text-sm text-gray-500 mt-1">{venue.address}</p>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div>
                        <h3 className="text-lg font-semibold mb-3">
                            {selectedVenue
                                ? `Games at ${selectedVenue.name}`
                                : 'Select a venue to see games'}
                        </h3>

                        {selectedVenue ? (
                            <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
                                {selectedVenue.games.map(game => {
                                    const isMentoneHome = game.home_team?.name?.includes('Mentone');
                                    const isMentoneAway = game.away_team?.name?.includes('Mentone');

                                    return (
                                        <div key={game.id} className="p-3 border border-gray-200 rounded">
                                            <div className="text-sm text-gray-500 mb-2">
                                                {formatGameDate(game.date)}
                                            </div>

                                            <div className="flex justify-between items-center">
                                                <div>
                                                    <div className={isMentoneHome ? "font-semibold text-blue-600" : ""}>
                                                        {game.home_team?.name}
                                                    </div>
                                                    <div className="text-xs text-gray-500 my-1">vs</div>
                                                    <div className={isMentoneAway ? "font-semibold text-blue-600" : ""}>
                                                        {game.away_team?.name}
                                                    </div>
                                                </div>

                                                <div>
                                                    {game.status === 'completed' ? (
                                                        <div className="text-center">
                                                            <div className="text-lg font-bold">
                                                                {game.home_team?.score} - {game.away_team?.score}
                                                            </div>
                                                            <div className="text-xs bg-green-100 text-green-800 rounded px-2 py-1">
                                                                Final
                                                            </div>
                                                        </div>
                                                    ) : (
                                                        <div className="text-xs bg-blue-100 text-blue-800 rounded px-2 py-1">
                                                            {game.status === 'in_progress' ? 'In Progress' : 'Scheduled'}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        ) : (
                            <div className="text-center py-8 text-gray-500 border border-gray-200 rounded">
                                Select a venue from the list to view scheduled games
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ClubVenues;