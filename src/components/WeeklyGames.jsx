import React, { useState, useEffect } from 'react';
import { format, startOfWeek, endOfWeek, addWeeks, subWeeks, isToday } from 'date-fns';
import {
    fetchGamesByDateRange,
    groupGamesByCategory
} from '../services/firestoreService';

const WeeklyGames = () => {
    const [games, setGames] = useState([]);
    const [loading, setLoading] = useState(true);
    const [currentWeekStart, setCurrentWeekStart] = useState(() => startOfWeek(new Date(), { weekStartsOn: 1 })); // Start on Monday
    const currentWeekEnd = endOfWeek(currentWeekStart, { weekStartsOn: 1 });

    // Fetch games for the selected week
    useEffect(() => {
        const fetchWeeklyGames = async () => {
            setLoading(true);

            try {
                // Use our service function to fetch games
                const gamesData = await fetchGamesByDateRange(
                    currentWeekStart,
                    currentWeekEnd,
                    'club_mentone' // Optionally filter by Mentone club
                );

                setGames(gamesData);
            } catch (error) {
                console.error("Error fetching weekly games:", error);
            } finally {
                setLoading(false);
            }
        };

        fetchWeeklyGames();
    }, [currentWeekStart, currentWeekEnd]);

    // Navigate to previous week
    const goToPreviousWeek = () => {
        setCurrentWeekStart(prev => subWeeks(prev, 1));
    };

    // Navigate to next week
    const goToNextWeek = () => {
        setCurrentWeekStart(prev => addWeeks(prev, 1));
    };

    // Go to current week
    const goToCurrentWeek = () => {
        setCurrentWeekStart(startOfWeek(new Date(), { weekStartsOn: 1 }));
    };

    // Group games by category using our service function
    const groupedGames = groupGamesByCategory(games);

    // Format dates for display
    const formattedDateRange = `${format(currentWeekStart, 'MMM d')} - ${format(currentWeekEnd, 'MMM d, yyyy')}`;

    // Get day of week function
    const getDayOfWeek = (date) => format(date, 'EEE');

    // Format time function
    const formatTime = (date) => format(date, 'h:mm a');

    return (
        <div className="bg-white rounded-lg shadow p-6">
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold text-blue-800">Weekly Games</h2>

                <div className="flex items-center space-x-2">
                    <button
                        onClick={goToPreviousWeek}
                        className="px-3 py-1 bg-gray-200 hover:bg-gray-300 rounded"
                    >
                        Previous
                    </button>

                    <button
                        onClick={goToCurrentWeek}
                        className="px-3 py-1 bg-blue-600 text-white hover:bg-blue-700 rounded"
                    >
                        Current Week
                    </button>

                    <button
                        onClick={goToNextWeek}
                        className="px-3 py-1 bg-gray-200 hover:bg-gray-300 rounded"
                    >
                        Next
                    </button>
                </div>
            </div>

            <div className="text-lg font-medium text-center mb-6">{formattedDateRange}</div>

            {loading ? (
                <div className="text-center py-8">Loading games...</div>
            ) : (
                <div className="space-y-8">
                    {Object.entries(groupedGames).map(([category, categoryGames]) => (
                        <div key={category} className="border-t pt-4">
                            <h3 className="text-xl font-semibold mb-3">{category}</h3>

                            {categoryGames.length > 0 ? (
                                <div className="overflow-x-auto">
                                    <table className="min-w-full divide-y divide-gray-200">
                                        <thead className="bg-gray-50">
                                        <tr>
                                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Day</th>
                                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
                                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Teams</th>
                                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Venue</th>
                                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                                        </tr>
                                        </thead>
                                        <tbody className="bg-white divide-y divide-gray-200">
                                        {categoryGames.map(game => {
                                            const isMentoneHome = game.home_team?.name?.includes('Mentone');
                                            const isMentoneAway = game.away_team?.name?.includes('Mentone');

                                            return (
                                                <tr key={game.id} className={isToday(game.date) ? "bg-blue-50" : ""}>
                                                    <td className="px-4 py-2 whitespace-nowrap text-sm">
                                                        {getDayOfWeek(game.date)}
                                                    </td>
                                                    <td className="px-4 py-2 whitespace-nowrap text-sm">
                                                        {formatTime(game.date)}
                                                    </td>
                                                    <td className="px-4 py-2 text-sm">
                                                        <div className={isMentoneHome ? "font-semibold text-blue-600" : ""}>
                                                            {game.home_team?.name}
                                                        </div>
                                                        <div className="text-gray-500">vs</div>
                                                        <div className={isMentoneAway ? "font-semibold text-blue-600" : ""}>
                                                            {game.away_team?.name}
                                                        </div>
                                                    </td>
                                                    <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">
                                                        {game.venue}
                                                    </td>
                                                    <td className="px-4 py-2 whitespace-nowrap text-sm">
                              <span className={`px-2 py-1 rounded text-xs font-medium ${
                                  game.status === 'completed'
                                      ? 'bg-green-100 text-green-800'
                                      : game.status === 'in_progress'
                                          ? 'bg-yellow-100 text-yellow-800'
                                          : 'bg-blue-100 text-blue-800'
                              }`}>
                                {game.status === 'completed'
                                    ? 'Final'
                                    : game.status === 'in_progress'
                                        ? 'In Progress'
                                        : 'Scheduled'}
                              </span>
                                                        {game.status === 'completed' && (
                                                            <div className="mt-1 text-sm">
                                                                {game.home_team?.score} - {game.away_team?.score}
                                                            </div>
                                                        )}
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                        </tbody>
                                    </table>
                                </div>
                            ) : (
                                <p className="text-gray-500 py-2">No {category.toLowerCase()} games this week</p>
                            )}
                        </div>
                    ))}

                    {games.length === 0 && (
                        <div className="text-center py-8 text-gray-500">
                            No games scheduled for this week
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default WeeklyGames;