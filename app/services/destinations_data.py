"""Curated destinations for the Explore page.

Static data on purpose: it loads instantly, costs nothing, and gives the
planner form something to prefill. `image` is optional - drop a file into
app/static/images/ and set the filename to replace the gradient artwork.
"""

DESTINATIONS = [
    {
        "slug": "goa",
        "coords": [15.2993, 74.124],
        "name": "Goa",
        "country": "India",
        "tagline": "Beaches, cafes and a slow coastal week",
        "description": "Sunsets over the Arabian Sea, Portuguese-era churches, beach shacks and a night market on every corner.",
        "best_time": "November - February",
        "avg_budget": 25000,
        "duration": "4-5 days",
        "tags": ["Beaches", "Nightlife", "Food"],
        "icon": "bi-umbrella",
        "gradient": ["#ff9966", "#ff5e62"],
        "image": None,
    },
    {
        "slug": "manali",
        "coords": [32.2432, 77.1892],
        "name": "Manali",
        "country": "India",
        "tagline": "Snow peaks, pine forests and mountain cafes",
        "description": "The classic Himalayan escape - Solang Valley, Old Manali cafes and a drive up to Atal Tunnel.",
        "best_time": "March - June, December - January",
        "avg_budget": 22000,
        "duration": "5-6 days",
        "tags": ["Mountains", "Trekking", "Adventure"],
        "icon": "bi-snow2",
        "gradient": ["#3a7bd5", "#00d2ff"],
        "image": None,
    },
    {
        "slug": "jaipur",
        "coords": [26.9124, 75.7873],
        "name": "Jaipur",
        "country": "India",
        "tagline": "Forts, bazaars and the Pink City glow",
        "description": "Amber Fort at sunrise, City Palace, Hawa Mahal and the best street food in Rajasthan.",
        "best_time": "October - March",
        "avg_budget": 18000,
        "duration": "3-4 days",
        "tags": ["Historical Places", "Local Culture", "Shopping"],
        "icon": "bi-building",
        "gradient": ["#f7971e", "#ffd200"],
        "image": None,
    },
    {
        "slug": "kashmir",
        "coords": [34.0837, 74.7973],
        "name": "Kashmir",
        "country": "India",
        "tagline": "Houseboats, meadows and Himalayan light",
        "description": "Dal Lake shikara rides, Gulmarg gondola, Pahalgam valleys and Mughal gardens in bloom.",
        "best_time": "April - October",
        "avg_budget": 35000,
        "duration": "6-7 days",
        "tags": ["Nature", "Mountains", "Photography"],
        "icon": "bi-tree",
        "gradient": ["#0f9b8e", "#38ef7d"],
        "image": None,
    },
    {
        "slug": "kerala",
        "coords": [9.9312, 76.2673],
        "name": "Kerala",
        "country": "India",
        "tagline": "Backwaters, tea hills and Ayurveda",
        "description": "Alleppey houseboats, Munnar tea estates, Fort Kochi lanes and a coastline that never rushes.",
        "best_time": "September - March",
        "avg_budget": 30000,
        "duration": "6-7 days",
        "tags": ["Nature", "Relaxation", "Food"],
        "icon": "bi-water",
        "gradient": ["#11998e", "#38ef7d"],
        "image": None,
    },
    {
        "slug": "mumbai",
        "coords": [19.076, 72.8777],
        "name": "Mumbai",
        "country": "India",
        "tagline": "The city that never slows down",
        "description": "Marine Drive at night, Colaba heritage walks, Elephanta caves and street food worth the queue.",
        "best_time": "October - February",
        "avg_budget": 20000,
        "duration": "3-4 days",
        "tags": ["Food", "Nightlife", "Shopping"],
        "icon": "bi-buildings",
        "gradient": ["#8e2de2", "#4a00e0"],
        "image": None,
    },
    {
        "slug": "delhi",
        "coords": [28.6139, 77.209],
        "name": "Delhi",
        "country": "India",
        "tagline": "Seven centuries in one city",
        "description": "Red Fort, Humayun's Tomb, Chandni Chowk food walks and Lodhi Garden mornings.",
        "best_time": "October - March",
        "avg_budget": 16000,
        "duration": "3-4 days",
        "tags": ["Historical Places", "Food", "Museums"],
        "icon": "bi-bank",
        "gradient": ["#c31432", "#240b36"],
        "image": None,
    },
    {
        "slug": "rishikesh",
        "coords": [30.0869, 78.2676],
        "name": "Rishikesh",
        "country": "India",
        "tagline": "Rapids, yoga and the Ganga at dusk",
        "description": "River rafting, Laxman Jhula, riverside cafes and the evening Ganga Aarti at Triveni Ghat.",
        "best_time": "September - November, February - May",
        "avg_budget": 14000,
        "duration": "3-4 days",
        "tags": ["Adventure", "Nature", "Trekking"],
        "icon": "bi-water",
        "gradient": ["#2193b0", "#6dd5ed"],
        "image": None,
    },
    {
        "slug": "udaipur",
        "coords": [24.5854, 73.7125],
        "name": "Udaipur",
        "country": "India",
        "tagline": "Lakes, palaces and rooftop dinners",
        "description": "City Palace, Lake Pichola boat rides, Bagore Ki Haveli dances and the most romantic sunsets in Rajasthan.",
        "best_time": "September - March",
        "avg_budget": 22000,
        "duration": "3-4 days",
        "tags": ["Romantic", "Historical Places", "Photography"],
        "icon": "bi-heart",
        "gradient": ["#ee9ca7", "#b06ab3"],
        "image": None,
    },
    {
        "slug": "bali",
        "coords": [-8.65, 115.2167],
        "name": "Bali",
        "country": "Indonesia",
        "tagline": "Rice terraces, temples and surf towns",
        "description": "Ubud jungle mornings, Uluwatu cliffs, Nusa islands and warungs that cost next to nothing.",
        "best_time": "April - October",
        "avg_budget": 85000,
        "duration": "7-8 days",
        "tags": ["Beaches", "Nature", "Photography"],
        "icon": "bi-flower1",
        "gradient": ["#00b09b", "#96c93d"],
        "image": None,
    },
    {
        "slug": "dubai",
        "coords": [25.2048, 55.2708],
        "name": "Dubai",
        "country": "UAE",
        "tagline": "Desert dunes and skyline nights",
        "description": "Burj Khalifa, a desert safari at golden hour, the old Gold Souk and a dhow dinner cruise.",
        "best_time": "November - March",
        "avg_budget": 95000,
        "duration": "5-6 days",
        "tags": ["Luxury", "Shopping", "Adventure"],
        "icon": "bi-brightness-high",
        "gradient": ["#eacda3", "#d6ae7b"],
        "image": None,
    },
    {
        "slug": "paris",
        "coords": [48.8566, 2.3522],
        "name": "Paris",
        "country": "France",
        "tagline": "Museums, boulevards and long lunches",
        "description": "The Louvre, Montmartre mornings, Seine walks and a picnic under the Eiffel Tower.",
        "best_time": "April - June, September - October",
        "avg_budget": 150000,
        "duration": "6-7 days",
        "tags": ["Museums", "Romantic", "Local Culture"],
        "icon": "bi-camera",
        "gradient": ["#667eea", "#764ba2"],
        "image": None,
    },
]

_BY_SLUG = {item["slug"]: item for item in DESTINATIONS}
_BY_NAME = {item["name"].lower(): item for item in DESTINATIONS}


def all_destinations():
    return DESTINATIONS


def get_destination(slug):
    return _BY_SLUG.get((slug or "").lower())


def popular(limit=6):
    return DESTINATIONS[:limit]


def find_by_name(name):
    """Match a free-text destination against the catalogue (exact, then prefix).

    Used by the weather service so that "Goa" resolves to Goa, India rather
    than whatever a fuzzy geocoder ranks first.
    """
    key = (name or "").strip().lower()
    if not key:
        return None
    if key in _BY_NAME:
        return _BY_NAME[key]
    for item in DESTINATIONS:
        candidate = item["name"].lower()
        if key.startswith(candidate + ",") or key.startswith(candidate + " "):
            return item
    return None
