DOMAIN = "ov_9292"

API_URL = "https://web-api.9292.nl/api/v1/plans"

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
CONF_ROUTE_PERSON = "person"
CONF_EXCLUDED_MODES = "excluded_modes"
CONF_EXTRA_INTERCHANGE_TIME = "extra_interchange_time"
CONF_ACCESSIBILITY = "accessibility"
CONF_LESS_WALKING = "less_walking"

# Travel modes as the 9292 API names them (used in excludedTravelModes)
TRAVEL_MODES = ["Bus", "Ferry", "OnDemand", "Subway", "Train", "Tram", "WithSurcharge"]

# Number of later options requested next to the first one
PLANS_AFTER = 5
# Options listed as an attribute of the summary sensor
UPCOMING_LIMIT = 5
