# An automated tool to detect suspicious Instagram profiles by analyzing profile data, engagement patterns, and bio content

import instaloader

# Initialize Instaloader
L = instaloader.Instaloader()

# Function to scrape profile information
def scrape_instagram_profile(username):
    try:
        # Load the profile
        profile = instaloader.Profile.from_username(L.context, username)
        
        # Print basic profile information
        print(f"👤 Username: {profile.username}")
        print(f"📛 Full Name: {profile.full_name}")
        print(f"📜 Bio: {profile.biography}")
        print(f"🌐 Website: {profile.external_url}")
        print(f"🖼️ Profile Pic URL: {profile.profile_pic_url}")
        print(f"📅 Account Created: {profile.date_joined}")
        print(f"📝 Posts: {profile.mediacount}")
        print(f"👥 Followers: {profile.followers}")
        print(f"➡️ Following: {profile.followees}")
        
        # Follower/Following ratio
        if profile.followees != 0:
            ratio = profile.followers / profile.followees
            print(f"📊 Follower/Following Ratio: {ratio:.2f}")
        else:
            print("📊 Follower/Following Ratio: N/A (no followees)")

        # Check if the account is private
        print(f"🔐 Private Account: {profile.is_private}")
        
        # Profile insights (this can vary depending on the account)
        print(f"🏅 Is Verified: {profile.is_verified}")

    except Exception as e:
        print(f"Error: {e}")

# Test with a sample Instagram username
username = "denulah"  # Replace with any Instagram username you want to test
scrape_instagram_profile(username)
