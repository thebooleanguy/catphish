from flask import Flask, render_template, request
import instaloader
import threading
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from time import sleep
import os

app = Flask(__name__)
L = instaloader.Instaloader()

# --- Reverse image search (run in background thread) ---
def reverse_image_search(image_path, result_holder):
    try:
        options = Options()
        options.add_argument("--headless")
        driver = webdriver.Firefox(options=options)

        driver.get("https://images.google.com")
        sleep(3)
        result = {"match_found": False, "status": "Could not determine", "score": 0}

        driver.find_element(By.XPATH, "//div[@aria-label='Search by image']").click()
        sleep(2)
        upload_input = driver.find_element(By.XPATH, "//input[@type='file']")
        upload_input.send_keys(image_path)
        sleep(7)

        try:
            match_div = driver.find_element(By.XPATH, "/html/body/div[3]/div/div[4]/div/div/div/div/div[1]/div/div/div/div/div[1]/div[1]/div[5]/a/div")
            if match_div:
                result.update({"match_found": True, "status": "⚠️ Image match found!", "score": 1})
        except:
            try:
                no_match = driver.find_element(By.XPATH, "//div[contains(text(), 'No other sizes')]")
                if no_match:
                    result.update({"status": "✅ No image matches found.", "score": 0})
            except:
                result["status"] = "ℹ️ Could not confirm match result."

        driver.quit()
        result_holder["result"] = result

    except Exception as e:
        print("❌ Reverse image search error:", e)
        result_holder["result"] = {"match_found": False, "status": "Reverse search failed", "score": 0}

# --- Profile analysis ---
def analyze_profile(username):
    score = 0
    max_score = 10
    breakdown = []

    try:
        profile = instaloader.Profile.from_username(L.context, username)

        bio = profile.biography or ""
        if not bio:
            breakdown.append(("📝 Empty Bio", "+1"))
            score += 1
        else:
            emoji_count = sum(1 for c in bio if c in "❤️🔥💯😘😍🌹👉👇😎😊")
            if len(bio) < 5:
                breakdown.append(("✏️ Suspiciously Short Bio", "+1"))
                score += 1
            if emoji_count >= 3:
                breakdown.append(("🤖 Too Many Emojis", "+1"))
                score += 1

        if profile.mediacount == 0:
            breakdown.append(("📭 No Posts", "+2"))
            score += 2
        elif profile.mediacount < 3:
            breakdown.append(("📸 Low Post Count", "+1"))
            score += 1

        if profile.followees > 0:
            ratio = profile.followers / profile.followees
            if ratio > 10:
                breakdown.append(("📈 Very High Follower Ratio", "+2"))
                score += 2
            elif ratio < 0.1:
                breakdown.append(("📉 Very Low Follower Ratio", "+2"))
                score += 2
            elif ratio < 0.5 or ratio > 3:
                breakdown.append(("⚖️ Unbalanced Follower Ratio", "+1"))
                score += 1
        else:
            breakdown.append(("🚩 Follows No One", "+2"))
            score += 2

        if profile.is_private:
            breakdown.append(("🔐 Private Profile", "+1"))
            score += 1

        percentage = int((score / max_score) * 100)
        return score, max_score, percentage, breakdown

    except Exception as e:
        print("❌ Profile analysis error:", e)
        return 0, 10, 0, [("❌ Failed to analyze profile", "+0")]

# --- Download profile picture ---
def download_profile_pic(username):
    try:
        L.download_profile(username, profile_pic_only=True)
        folder = os.path.join(os.getcwd(), username)
        for file in os.listdir(folder):
            if file.endswith(".jpg"):
                return os.path.join(folder, file)
    except Exception as e:
        print("❌ Profile pic download error:", e)
    return None

# --- Render detection ---
def render_detection(username):
    profile_pic = download_profile_pic(username)
    score, max_score, percentage, breakdown = analyze_profile(username)

    reverse_result = {"status": "Loading reverse image search...", "score": 0}
    result_holder = {}

    if profile_pic:
        thread = threading.Thread(target=reverse_image_search, args=(profile_pic, result_holder))
        thread.start()
    else:
        reverse_result["status"] = "Profile picture not found."

    return render_template('detection.html',
                           username=username,
                           score=score,
                           max_score=max_score,
                           percentage=percentage,
                           reverse_result=reverse_result,
                           breakdown=breakdown)

# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scan', methods=['POST'])
def scan():
    username = request.form.get("username", "").strip()
    return render_detection(username)

@app.route('/detection')
def detection():
    username = request.args.get("username", "").strip()
    return render_detection(username)

if __name__ == '__main__':
    app.run(debug=True)
