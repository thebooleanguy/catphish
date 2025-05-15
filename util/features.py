import numpy as np

def extract_features_for_model(profile):
    try:
        features = {
            "statuses_count": profile.mediacount,
            "followers_count": profile.followers,
            "friends_count": profile.followees,
            "favourites_count": 0,  # Not available on IG
            "listed_count": 0,     # Not available
            "geo_enabled": int(not profile.is_private),
            "profile_use_background_image": 1,
            "lang": 0  # Simplified
        }
        return np.array([[features[k] for k in features]])
    except Exception as e:
        print("Error generating ML features:", e)
        return np.zeros((1, 8))
