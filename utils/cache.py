from cachetools import TTLCache
# In memory caches
overpass_cache = TTLCache(maxsize=256, ttl=6) # 5 min
alerts_cache = TTLCache(maxsize=64, ttl=180) # 3 min
transtar_cache = TTLCache(maxsize=64, ttl=180) # 2 min