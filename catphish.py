import instaloader
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from time import sleep
import os
from textblob import TextBlob

L = instaloader.Instaloader()

# --- Step 1: Download profile pic ---
def download_profile_pic(username):
    try:
        L.download_profile(username, profile_pic_only=True)
        folder = os.path.join(os.getcwd(), username)
        for file in os.listdir(folder):
            if file.endswith('.jpg'):
                return os.path.join(folder, file)
    except Exception as e:
        print(f"❌ Failed to download profile picture: {e}")
        return None

# --- Step 2: Reverse image search using Selenium ---
def reverse_image_search(image_path):
    options = Options()
    options.set_preference("dom.webdriver.enabled", False)
    driver = webdriver.Firefox(options=options)

    driver.get("https://images.google.com")
    sleep(4)

    try:
        search_btn = driver.find_element(By.XPATH, "//div[@aria-label='Search by image']")
        search_btn.click()
        sleep(2)

        upload_input = driver.find_element(By.XPATH, "//input[@type='file']")
        upload_input.send_keys(image_path)
        sleep(8)

        # Scroll to reveal matches
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        sleep(2)

        result = {"match_found": False, "status": "Could not determine"}
        try:
            match_div = driver.find_element(By.XPATH, "/html/body/div[3]/div/div[4]/div/div/div/div/div[1]/div/div/div/div/div[1]/div[1]/div[5]/a/div")
            if match_div:
                result["match_found"] = True
                result["status"] = "⚠️ Image match found on the web!"
        except:
            try:
                no_match_text = driver.find_element(By.XPATH, "//div[contains(text(), 'No other sizes of this image found') or contains(text(), 'No matches for your search')]")
                if no_match_text:
                    result["status"] = "✅ No exact image matches found."
            except:
                result["status"] = "ℹ️ Could not confirm match result. Please verify manually."

        return driver, result

    except Exception as e:
        print("❌ Image upload/search failed:", e)
        return None, {"match_found": False, "status": "❌ Failed to perform reverse image search"}

# --- Step 3: Profile analysis and scoring ---
def analyze_profile(username):
    profile_data = {}
    score = 0
    max_score = 10  # Adjusted total based on refined logic
    breakdown = []

    try:
        profile = instaloader.Profile.from_username(L.context, username)
        profile_data = {
            "username": profile.username,
            "full_name": profile.full_name,
            "bio": profile.biography,
            "followers": profile.followers,
            "following": profile.followees,
            "posts": profile.mediacount,
            "is_private": profile.is_private,
        }

        # --- Bio analysis ---
        if not profile.biography:
            breakdown.append(("📝 Empty bio", "+1"))
            score += 1
        else:
            blob = TextBlob(profile.biography)
            try:
                lang = blob.detect_language()
                if lang == 'en':
                    emoji_count = sum(1 for c in profile.biography if c in "❤️🔥💯😘😍🌹👉👇😎😊")
                    if len(profile.biography) < 5:
                        breakdown.append(("✏️ Suspiciously short bio", "+1"))
                        score += 1
                    if emoji_count >= 3:
                        breakdown.append(("🤖 Too many emojis/symbols", "+1"))
                        score += 1
            except Exception:
                breakdown.append(("🌐 Language detection failed", "+0"))

        # --- Post count ---
        if profile.mediacount == 0:
            breakdown.append(("📭 No posts at all", "+2"))
            score += 2
        elif profile.mediacount < 3:
            breakdown.append(("📸 Very low post count", "+1"))
            score += 1

        # --- Follower / Following ratio ---
        if profile.followees > 0:
            ratio = profile.followers / profile.followees
            if ratio > 10:
                breakdown.append(("📈 Unnaturally high follower ratio", "+2"))
                score += 2
            elif ratio < 0.1:
                breakdown.append(("📉 Very low follower ratio", "+2"))
                score += 2
            elif ratio < 0.5 or ratio > 3:
                breakdown.append(("⚠️ Unbalanced follower ratio", "+1"))
                score += 1
        else:
            breakdown.append(("🚩 Follows no one", "+2"))
            score += 2

        # --- Privacy status ---
        if profile.is_private:
            breakdown.append(("🔐 Private profile", "+1"))
            score += 1

        # Final percentage
        percentage = int((score / max_score) * 100)

        return profile_data, breakdown, score, max_score, percentage
    except Exception as e:
        print(f"❌ Error analyzing profile: {e}")
        return {}, [], 0, max_score, 0


# --- Run everything together ---
if __name__ == "__main__":
    username = input("Enter Instagram username: ").strip()
    img_path = download_profile_pic(username)

    if img_path:
        print(f"\n📥 Profile picture downloaded: {img_path}")
        print("🌐 Performing reverse image search...")
        driver, reverse_result = reverse_image_search(img_path)

        # Just display image result – not used in scoring
        print(f"\n🔁 Reverse Image Search Result:")
        print(f"{reverse_result['status']}")
        print("📝 Note: Image match result is for manual inspection only – not included in score.\n")

        print("📊 Profile Heuristic Analysis:")
        analyze_profile(username)

        print("\n🧠 Done! Browser window remains open for your review.")
    else:
        print("❌ Could not process the profile.")
