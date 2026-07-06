# config.py

FEEDS = [
    ("The Hacker News", "https://feeds.feedburner.com/TheHackersNews?format=xml"),
    ("Krebs on Security", "https://krebsonsecurity.com/feed/"),
    ("0day Fans", "https://0dayfans.com/feed.rss")
]

# Maximum number of articles to fetch per RSS feed
MAX_ARTICLES_PER_FEED = 10

# Maximum number of web search results per topic
MAX_WEB_RESULTS = 5

# Number of days to look back when keeping articles
LOOKBACK_DAYS = 7

# Whether RSS article titles should be expanded with Serper web search
EXPAND_FEED_TOPICS_WITH_SERPER = False

# Number of top RSS articles per source to expand
SEARCHES_PER_SOURCE = 3

# Minimum number of articles for a cluster to be saved
MIN_CLUSTER_ARTICLES = 1

# Embedding similarity threshold for clustering (0-1)
SIMILARITY_THRESHOLD = 0.75

# Optional: Logging verbosity
VERBOSE = True

# Serper API key is injected from the local runtime configuration.
SERPER_API_KEY = None
