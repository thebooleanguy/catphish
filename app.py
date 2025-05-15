from flask import Flask, render_template, request, jsonify, url_for, send_from_directory
import instaloader
import webbrowser
import threading
import platform
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from time import sleep
import os
import shutil

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
L = instaloader.Instaloader()

# Create static profile pics directory if not exists
PROFILE_PICS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'profile_pics')
if not os.path.exists(PROFILE_PICS_DIR):
    os.makedirs(PROFILE_PICS_DIR)

# --- Reverse image search (run in background thread) ---
def reverse_image_search(image_path, result_holder):
    try:
        system = platform.system()
        driver = None

        if system == "Windows":
            chrome_options = ChromeOptions()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            driver = webdriver.Chrome(options=chrome_options)
        elif system == "Linux":
            firefox_options = FirefoxOptions()
            firefox_options.add_argument("--headless")
            driver = webdriver.Firefox(options=firefox_options)
        else:
            raise Exception(f"Unsupported OS: {system}")

        driver.get("https://images.google.com")
        sleep(3)

        result = {"match_found": False, "status": "Could not determine", "score": 0}

        # Click "Search by image"
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

    except WebDriverException as e:
        print("❌ Selenium WebDriver error:", e)
        result_holder["result"] = {"match_found": False, "status": f"Selenium error: {e}", "score": 0}
    except Exception as e:
        print("❌ Reverse image search error:", e)
        result_holder["result"] = {"match_found": False, "status": f"Error: {e}", "score": 0}
    finally:
        try:
            if driver:
                driver.quit()
        except:
            pass


# --- Profile analysis ---
def analyze_profile(username):
    score = 0
    max_score = 10
    breakdown = []
    profile_data = {}
    
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        
        # Store profile details
        profile_data = {
            "username": profile.username,
            "full_name": profile.full_name,
            "bio": profile.biography or "No biography",
            "external_url": profile.external_url or "None",
            "followers": profile.followers,
            "followees": profile.followees,
            "mediacount": profile.mediacount,
            "is_private": profile.is_private,
            "is_verified": profile.is_verified,
            "profile_pic_url": profile.profile_pic_url
        }
        
        bio = profile.biography or ""
        if not bio:
            breakdown.append(("📝 Empty Bio", "+1", "No personal description provided"))
            score += 1
        else:
            emoji_count = sum(1 for c in bio if c in "❤️🔥💯😘😍🌹👉👇😎😊")
            if len(bio) < 5:
                breakdown.append(("✏️ Suspiciously Short Bio", "+1", "Bio is unusually brief"))
                score += 1
            if emoji_count >= 3:
                breakdown.append(("🤖 Too Many Emojis", "+1", f"{emoji_count} emojis detected"))
                score += 1
        
        if profile.mediacount == 0:
            breakdown.append(("📭 No Posts", "+2", "Account has no content"))
            score += 2
        elif profile.mediacount < 3:
            breakdown.append(("📸 Low Post Count", "+1", f"Only {profile.mediacount} posts"))
            score += 1
        
        if profile.followees > 0:
            ratio = profile.followers / profile.followees
            ratio_formatted = f"{ratio:.2f}"
            if ratio > 10:
                breakdown.append((
                    "📈 Very High Follower Ratio", 
                    "+2", 
                    f"Ratio: {ratio_formatted} ({profile.followers} followers, {profile.followees} following)"
                ))
                score += 2
            elif ratio < 0.1:
                breakdown.append((
                    "📉 Very Low Follower Ratio", 
                    "+2", 
                    f"Ratio: {ratio_formatted} ({profile.followers} followers, {profile.followees} following)"
                ))
                score += 2
            elif ratio < 0.5 or ratio > 3:
                breakdown.append((
                    "⚖️ Unbalanced Follower Ratio", 
                    "+1", 
                    f"Ratio: {ratio_formatted} ({profile.followers} followers, {profile.followees} following)"
                ))
                score += 1
        else:
            breakdown.append(("🚩 Follows No One", "+2", "Account doesn't follow anyone"))
            score += 2
        
        if profile.is_private:
            breakdown.append(("🔐 Private Profile", "+1", "Content not publicly visible"))
            score += 1
        
        if not profile.is_verified and profile.followers > 10000:
            breakdown.append(("🔍 High Followers but Not Verified", "+1", f"{profile.followers} followers without verification"))
            score += 1
        
        percentage = int((score / max_score) * 100)
        return score, max_score, percentage, breakdown, profile_data
    
    except Exception as e:
        print("❌ Profile analysis error:", e)
        return 0, 10, 0, [("❌ Failed to analyze profile", "+0", str(e))], {}

# --- Download profile picture ---
def download_profile_pic(username):
    try:
        # Create static folder for profile pictures if it doesn't exist
        if not os.path.exists(PROFILE_PICS_DIR):
            os.makedirs(PROFILE_PICS_DIR)
        
        # Set target file path
        dest_file = os.path.join(PROFILE_PICS_DIR, f"{username}.jpg")
        
        # Check if profile pic already exists
        if os.path.exists(dest_file):
            return dest_file
        
        # Download profile picture
        profile = instaloader.Profile.from_username(L.context, username)
        L.download_profilepic(profile)
        
        # Find the downloaded file in the username directory
        folder = os.path.join(os.getcwd(), username)
        if os.path.exists(folder):
            for file in os.listdir(folder):
                if file.endswith(".jpg"):
                    src_file = os.path.join(folder, file)
                    shutil.copy2(src_file, dest_file)
                    shutil.rmtree(folder)  # Clean up original download folder
                    return dest_file
    except Exception as e:
        print("❌ Profile pic download error:", e)
    return None

# --- Check if reverse search is complete and return results ---
@app.route('/check_reverse_search')
def check_reverse_search():
    result_holder = app.config.get('result_holder', {})
    if 'result' in result_holder:
        return jsonify(result_holder['result'])
    return jsonify({"status": "Processing...", "score": 0})

# --- Serve profile pictures from static folder ---
@app.route('/static/profile_pics/<filename>')
def profile_pic(filename):
    return send_from_directory(PROFILE_PICS_DIR, filename)

# --- Render detection ---
def render_detection(username):
    app.config['result_holder'] = {}  # Reset result holder
    result_holder = app.config['result_holder']
    
    # Analyze profile
    score, max_score, percentage, breakdown, profile_data = analyze_profile(username)
    
    # Download and set profile picture URL
    profile_pic_path = download_profile_pic(username)
    if profile_pic_path:
        # Convert to relative URL path for template
        profile_pic_url = url_for('static', filename=f'profile_pics/{username}.jpg')
        profile_data['local_profile_pic'] = profile_pic_url
    
    # Start reverse image search in background
    reverse_result = {"status": "Loading reverse image search...", "score": 0}
    
    if profile_pic_path:
        thread = threading.Thread(target=reverse_image_search, args=(profile_pic_path, result_holder))
        thread.daemon = True
        thread.start()
    else:
        reverse_result["status"] = "Profile picture not found."
    
    # Calculate risk level
    risk_level = "Low"
    if percentage >= 70:
        risk_level = "High"
    elif percentage >= 40:
        risk_level = "Medium"
    
    return render_template('detection.html',
                          username=username,
                          score=score,
                          max_score=max_score,
                          percentage=percentage,
                          risk_level=risk_level,
                          reverse_result=reverse_result,
                          breakdown=breakdown,
                          profile_data=profile_data)

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
    # Open browser in a separate thread after small delay
    def open_browser():
        sleep(1)
        webbrowser.open("http://127.0.0.1:5000")

    threading.Thread(target=open_browser).start()
    app.run(debug=True)
