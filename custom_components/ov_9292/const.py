DOMAIN = "ov_9292"

API_BASE_URL = "https://web-api.9292.nl"

CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 5  # minutes
MIN_SCAN_INTERVAL = 1
MAX_SCAN_INTERVAL = 60

# Routes live in the entry options as a list of
# {"id", "name", "from", "to", optional "person", "excluded_modes", ...}
CONF_ROUTES = "routes"
CONF_ROUTE_NAME = "name"
CONF_ROUTE_FROM = "from"
CONF_ROUTE_TO = "to"
# Next to the 9292 id of each end the route keeps its label and [lat, lon] for the card
ROUTE_ENDS = ("from", "to")
CONF_ROUTE_PERSON = "person"
CONF_EXCLUDED_MODES = "excluded_modes"
CONF_EXTRA_INTERCHANGE_TIME = "extra_interchange_time"
CONF_ACCESSIBILITY = "accessibility"
CONF_LESS_WALKING = "less_walking"

# Travel modes: option key (valid translation key) -> name in the 9292 API's excludedTravelModes
TRAVEL_MODES = {
    "bus": "Bus",
    "ferry": "Ferry",
    "on_demand": "OnDemand",
    "subway": "Subway",
    "train": "Train",
    "tram": "Tram",
    "with_surcharge": "WithSurcharge",
}

# Number of later options requested next to the first one
PLANS_AFTER = 5
# Options listed as an attribute of the summary sensor
UPCOMING_LIMIT = 5

SIGNAL_READY = f"{DOMAIN}_ready"

# Locations offered after a search
LOCATION_ROWS = 10
