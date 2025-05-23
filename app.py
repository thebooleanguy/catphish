from flask import Flask, render_template, request, jsonify, url_for, send_from_directory
import instaloader
import webbrowser
import threading
import platform
import pickle
import numpy as np
import pandas as pd
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
import re

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
L = instaloader.Instaloader()

# Create directories if they don't exist
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_PICS_DIR = os.path.join(BASE_DIR, 'static', 'profile_pics')
MODELS_DIR = os.path.join(BASE_DIR, 'models')

for directory in [PROFILE_PICS_DIR, MODELS_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

# Load the ML model if it exists, otherwise create a None placeholder
MODEL_PATH = os.path.join(MODELS_DIR, 'logistic_model.pkl')
ml_model = None
if os.path.exists(MODEL_PATH):
    try:
        ml_model = pickle.load(open(MODEL_PATH, 'rb'))
        print("✅ ML model loaded successfully")
    except Exception as e:
        print(f"❌ Error loading ML model: {e}")
else:
    print("⚠️ ML model not found. Some features will be limited.")

# --- Reverse image search (run in background thread) ---
def reverse_image_search(image_path, result_holder):
    try:
        # Set up Firefox options
        firefox_options = FirefoxOptions()
        firefox_options.set_preference("dom.webdriver.enabled", False)
        firefox_options.set_preference("useAutomationExtension", False)

        # Add additional preferences to help avoid detection
        firefox_options.set_preference('general.useragent.override', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36')
        firefox_options.set_preference("javascript.enabled", True)

        # Initialize the Firefox driver
        driver = webdriver.Firefox(options=firefox_options)
        print("✅ Firefox driver initialized")

        result = {"match_found": False, "status": "Processing...", "score": 0}
        result_holder["result"] = result  # Set initial status immediately

        # Navigate to Google Images
        driver.get("https://images.google.com")
        print("✅ Navigated to Google Images")

        # Wait for page to fully load
        sleep(3)

        try:
            # Check for CAPTCHA (common text in CAPTCHA pages)
            if "unusual traffic" in driver.page_source.lower() or "captcha" in driver.page_source.lower():
                print("⚠️ CAPTCHA detected before search")
                result.update({"status": "⚠️ CAPTCHA detected. Please solve the CAPTCHA in the browser window.", "score": 0})
                result_holder["result"] = result
                # Keep browser open for manual CAPTCHA solving
                # Wait indefinitely until user closes the browser or program exits
                try:
                    # Set a very long implicit wait so we don't consume CPU while waiting
                    driver.implicitly_wait(86400)  # 24 hours
                    print("🔍 Browser window left open for manual CAPTCHA solving")
                    return
                except:
                    # If there's an error (like user closed the browser), just return
                    return

            # Try to find and click the camera icon
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    # Look for camera icon with multiple possible selectors
                    selectors = [
                        "div.nDcEnd",
                        "div.LM8x9c",
                        "span.z1asCe svg",
                        "div.dRYYxd",
                        "//div[@aria-label='Search by image']",
                        "//span[@aria-label='Search by image']"
                    ]

                    for selector in selectors:
                        try:
                            if selector.startswith("//"):
                                camera_icon = driver.find_element(By.XPATH, selector)
                            else:
                                camera_icon = driver.find_element(By.CSS_SELECTOR, selector)
                            camera_icon.click()
                            print(f"✅ Found and clicked camera icon with selector: {selector}")
                            sleep(2)  # Wait for upload options to appear
                            break
                        except:
                            continue
                    else:
                        # If loop completes without breaking, no selector worked
                        print(f"⚠️ Attempt {attempt+1}: Camera icon not found with standard selectors")
                        # Try a JavaScript approach
                        try:
                            driver.execute_script("""
                                const buttons = document.querySelectorAll('div[role="button"]');
                                for (const button of buttons) {
                                    if (button.innerHTML.includes('svg')) {
                                        button.click();
                                        return true;
                                    }
                                }
                                return false;
                            """)
                            print("✅ Attempted JavaScript click on camera icon")
                            sleep(2)
                        except Exception as js_err:
                            print(f"❌ JavaScript click failed: {js_err}")

                    # Check if the click was successful by looking for upload options
                    upload_option_markers = [
                        "//input[@type='file']",
                        "//span[contains(text(), 'Upload an image')]",
                        "//div[contains(text(), 'Upload an image')]"
                    ]

                    for marker in upload_option_markers:
                        try:
                            driver.find_element(By.XPATH, marker)
                            print("✅ Upload option is visible, proceeding")
                            break
                        except:
                            continue
                    else:
                        if attempt < max_attempts - 1:
                            print(f"⚠️ Upload option not found on attempt {attempt+1}, retrying...")
                            sleep(2)
                            continue

                    # If we get here, either we found the upload option or we're on the last attempt
                    break

                except Exception as e:
                    print(f"❌ Error on attempt {attempt+1}: {e}")
                    if attempt < max_attempts - 1:
                        sleep(2)  # Wait before retrying
                    else:
                        raise  # Re-raise on last attempt

            # Now try to find the file upload input and upload the image
            try:
                upload_input = None
                upload_selectors = [
                    "//input[@type='file']",
                    "//input[@name='encoded_image']"
                ]

                for selector in upload_selectors:
                    try:
                        upload_input = driver.find_element(By.XPATH, selector)
                        print(f"✅ Found upload input with selector: {selector}")
                        break
                    except:
                        continue

                if upload_input:
                    abs_image_path = os.path.abspath(image_path)
                    upload_input.send_keys(abs_image_path)
                    print("✅ Image uploaded for reverse search")

                    # Wait for results - important to wait long enough
                    print("⏳ Waiting for search results...")
                    for i in range(10):  # Up to 10 seconds in 1-second increments
                        sleep(1)
                        # Check if results appear or if a CAPTCHA appeared
                        if "unusual traffic" in driver.page_source.lower() or "captcha" in driver.page_source.lower():
                            print("⚠️ CAPTCHA detected after upload")
                            result.update({"status": "⚠️ CAPTCHA challenge detected. Please solve the CAPTCHA in the browser window.", "score": 0})
                            result_holder["result"] = result
                            # Keep browser open for manual CAPTCHA solving
                            # Wait indefinitely until user closes the browser or program exits
                            try:
                                # Set a very long implicit wait so we don't consume CPU while waiting
                                driver.implicitly_wait(86400)  # 24 hours
                                print("🔍 Browser window left open for manual CAPTCHA solving")
                                return
                            except:
                                # If there's an error (like user closed the browser), just return
                                return

                        # Look for signs that results have loaded
                        result_indicators = [
                            "//div[contains(text(), 'Find image source')]",
                            "//div[contains(text(), 'Visually similar images')]",
                            "//div[contains(text(), 'Pages that include matching images')]",
                            "//div[contains(text(), 'No other sizes of this image found')]"
                        ]

                        for indicator in result_indicators:
                            try:
                                driver.find_element(By.XPATH, indicator)
                                print(f"✅ Results detected with indicator: {indicator}")
                                # Results found, break out of the wait loop
                                break
                            except:
                                continue
                        else:
                            # Continue waiting if no indicators found
                            print(f"⏳ Still waiting for results... ({i+1}s)")
                            continue

                        # If we get here, we found results and broke from the inner loop
                        break

                    # Now analyze the results
                    sleep(2)  # Additional wait to ensure all elements are loaded

                    # Scroll down to reveal all results
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
                    sleep(1)

                    # Check for specific matching images section
                    try:
                        driver.find_element(By.XPATH, "//div[contains(text(), 'Pages that include matching images')]")
                        print("✅ Match section found!")
                        result.update({"match_found": True, "status": "⚠️ Image match found! This profile picture exists elsewhere online.", "score": 1})
                    except:
                        try:
                            # Check for "visually similar" section
                            driver.find_element(By.XPATH, "//div[contains(text(), 'Visually similar images')]")
                            similar_count = len(driver.find_elements(By.XPATH, "//div[contains(@class, 'isv-r')]"))

                            if similar_count > 5:
                                print(f"✅ Found {similar_count} similar images")
                                result.update({"match_found": True, "status": f"⚠️ Found {similar_count} similar images online, possibly a stock or AI-generated image.", "score": 0.5})
                            else:
                                print("✅ Only a few similar images found")
                                result.update({"status": "✅ No exact matches found, only a few similar images.", "score": 0})
                        except:
                            try:
                                # Check for "no other sizes" message indicating unique image
                                driver.find_element(By.XPATH, "//div[contains(text(), 'No other sizes of this image found')]")
                                print("✅ No matches found")
                                result.update({"status": "✅ No image matches found. This appears to be a unique photo.", "score": 0})
                            except:
                                # Couldn't determine result confidently
                                print("⚠️ Could not clearly determine search results")
                                result.update({"status": "ℹ️ Could not confidently determine if this image exists elsewhere online.", "score": 0.3})
                else:
                    print("❌ Could not find upload input element")
                    result.update({"status": "❌ Failed to upload image for search.", "score": 0})

            except Exception as upload_error:
                print(f"❌ Error during file upload: {upload_error}")
                result.update({"status": f"❌ Error during image upload: {str(upload_error)}", "score": 0})

        except Exception as search_error:
            print(f"❌ Error during reverse search: {search_error}")
            result.update({"status": f"❌ Error during search: {str(search_error)}", "score": 0})

        driver.quit()
        print(f"🏁 Browser closed, reverse image search completed: {result}")
        result_holder["result"] = result

    except WebDriverException as e:
        print(f"❌ Selenium WebDriver error: {e}")
        result_holder["result"] = {"match_found": False, "status": f"❌ Browser automation error: {str(e)}", "score": 0}
    except Exception as e:
        print(f"❌ Reverse image search error: {e}")
        result_holder["result"] = {"match_found": False, "status": f"❌ Error: {str(e)}", "score": 0}


# --- Extract features for ML model ---
def extract_ml_features(profile):
    """Extract features for ML model from Instagram profile"""
    try:
        features = {}

        # 1. Profile picture (1 if exists, 0 if not)
        features['profile pic'] = 1  # Since we're looking at actual profiles

        # 2. Numbers in username ratio
        username = profile.username
        nums_in_username = sum(c.isdigit() for c in username)
        features['nums/length username'] = nums_in_username / len(username) if len(username) > 0 else 0

        # 3. Fullname word count
        fullname = profile.full_name or ""
        features['fullname words'] = len(fullname.split()) if fullname else 0

        # 4. Numbers in fullname ratio
        nums_in_fullname = sum(c.isdigit() for c in fullname)
        features['nums/length fullname'] = nums_in_fullname / len(fullname) if len(fullname) > 0 else 0

        # 5. Name equals username
        name_parts = fullname.lower().replace(" ", "")
        username_lower = username.lower()
        features['name==username'] = 1 if name_parts == username_lower else 0

        # 6. Description length
        bio = profile.biography or ""
        features['description length'] = len(bio)

        # 7. External URL
        features['external URL'] = 1 if profile.external_url else 0

        # 8. Private account
        features['private'] = 1 if profile.is_private else 0

        # 9. Post count
        features['#posts'] = profile.mediacount

        # 10. Followers count
        features['#followers'] = profile.followers

        # 11. Following count
        features['#follows'] = profile.followees

        return features

    except Exception as e:
        print(f"❌ Error extracting ML features: {e}")
        return None

# --- Profile analysis ---
def analyze_profile(username):
    score = 0
    max_score = 10
    breakdown = []
    profile_data = {}
    ml_prediction = None
    ml_probability = None

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

        # Run ML prediction if model is available
        if ml_model:
            features = extract_ml_features(profile)
            if features:
                # Convert dictionary to DataFrame with proper column order
                feature_df = pd.DataFrame([features])

                # Ensure the DataFrame has the same columns as the training data in the same order
                required_columns = ['profile pic', 'nums/length username', 'fullname words',
                                   'nums/length fullname', 'name==username', 'description length',
                                   'external URL', 'private', '#posts', '#followers', '#follows']

                for col in required_columns:
                    if col not in feature_df.columns:
                        feature_df[col] = 0

                feature_df = feature_df[required_columns]  # Ensure correct column order

                # Make prediction
                try:
                    ml_prediction = int(ml_model.predict(feature_df)[0])
                    ml_proba = ml_model.predict_proba(feature_df)[0]
                    ml_probability = round(float(ml_proba[ml_prediction]) * 100, 2)

                    # Add ML result to breakdown
                    if ml_prediction == 1:
                        breakdown.append(("🤖 ML Model Prediction", "+3", f"Fake account ({ml_probability}% confidence)"))
                        score += 3
                    else:
                        breakdown.append(("🤖 ML Model Prediction", "+0", f"Genuine account ({ml_probability}% confidence)"))
                except Exception as e:
                    print(f"❌ ML prediction error: {e}")

        # Continue with rule-based analysis
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

        # Normalize score to max_score
        percentage = min(int((score / max_score) * 100), 100)

        # Add ML prediction info to profile_data
        if ml_prediction is not None:
            profile_data["ml_prediction"] = ml_prediction
            profile_data["ml_probability"] = ml_probability

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

# --- Train and save ML model ---
@app.route('/train_model', methods=['GET'])
def train_model():
    try:
        # Check if sample data files exist
        train_file = os.path.join(BASE_DIR, 'data', 'train.csv')
        test_file = os.path.join(BASE_DIR, 'data', 'test.csv')

        if not os.path.exists(train_file) or not os.path.exists(test_file):
            return jsonify({
                "status": "error",
                "message": "Training data files not found. Place train.csv and test.csv in the 'data' folder."
            })

        # Import required libraries
        from sklearn.linear_model import LogisticRegression

        # Load data
        train_data = pd.read_csv(train_file)

        # Prepare data
        x_train = train_data.drop("fake", axis=1)
        y_train = train_data.loc[:, "fake"]

        # Train model
        model = LogisticRegression(max_iter=256)
        model.fit(x_train, y_train)

        # Save model
        if not os.path.exists(MODELS_DIR):
            os.makedirs(MODELS_DIR)

        pickle.dump(model, open(MODEL_PATH, 'wb'))

        # Update global model variable
        global ml_model
        ml_model = model

        return jsonify({
            "status": "success",
            "message": "ML model trained and saved successfully"
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error training model: {str(e)}"
        })

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

# --- Setup function to ensure proper environment ---
def setup_app():
    # Create necessary directories
    directories = [
        os.path.join(BASE_DIR, 'data'),
        os.path.join(BASE_DIR, 'models'),
        os.path.join(BASE_DIR, 'static'),
        os.path.join(BASE_DIR, 'templates')
    ]

    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)

    # Ensure we have a template directory with index.html
    index_template = os.path.join(BASE_DIR, 'templates', 'index.html')
    if not os.path.exists(index_template):
        with open(index_template, 'w') as f:
            f.write('''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Catphish – Instagram Fake Profile Detector</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet"/>
  <style>
    body {
      font-family: 'Inter', sans-serif;
      background: linear-gradient(135deg, #f3f4fc, #e7ebff);
      color: #333;
      padding: 2rem;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      margin: 0;
    }
    .card {
      background: #fff;
      padding: 2.5rem;
      border-radius: 1.5rem;
      box-shadow: 0 15px 40px rgba(0, 0, 0, 0.08);
      max-width: 500px;
      width: 100%;
    }
    h1 {
      text-align: center;
      font-size: 2rem;
      margin-bottom: 1.5rem;
    }
    h2 {
      text-align: center;
      font-size: 1.2rem;
      color: #6b7280;
      margin-top: -0.5rem;
      margin-bottom: 2rem;
    }
    .form-group {
      margin-bottom: 1.5rem;
    }
    label {
      display: block;
      margin-bottom: 0.5rem;
      font-weight: 500;
    }
    input {
      width: 100%;
      padding: 0.75rem;
      border: 2px solid #e5e7eb;
      border-radius: 0.5rem;
      font-size: 1rem;
      transition: border-color 0.2s;
    }
    input:focus {
      border-color: #4f46e5;
      outline: none;
    }
    button {
      display: block;
      width: 100%;
      padding: 0.75rem;
      background: #4f46e5;
      color: white;
      border: none;
      border-radius: 0.5rem;
      font-size: 1rem;
      font-weight: 500;
      cursor: pointer;
      transition: background-color 0.2s;
    }
    button:hover {
      background: #4338ca;
    }
    .footer {
      text-align: center;
      margin-top: 2rem;
      font-size: 0.875rem;
      color: #6b7280;
    }
    .hint {
      font-size: 0.875rem;
      color: #6b7280;
      margin-top: 0.5rem;
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>🐟 Catphish</h1>
    <h2>Instagram Fake Profile Detector</h2>

    <form action="/scan" method="post">
      <div class="form-group">
        <label for="username">Instagram Username</label>
        <input
          type="text"
          id="username"
          name="username"
          placeholder="Enter an Instagram username"
          required
        />
        <div class="hint">Enter a username without the @ symbol</div>
      </div>

      <button type="submit">Scan Profile</button>
    </form>

    <div class="footer">
      Powered by ML & OSINT techniques to detect fake Instagram profiles
    </div>
  </div>
</body>
</html>''')



# Open browser in a separate thread after small delay
def open_browser():
    sleep(2)  # Increased delay to ensure server is ready
    url = "http://127.0.0.1:5000"
    try:
        # First try the default browser opener
        webbrowser.open(url)
        print(f"✅ Browser opened at {url}")
    except Exception as e:
        # If that fails, try specific browsers based on platform
        print(f"Could not open default browser: {e}")
        try:
            system = platform.system()
            if system == "Windows":
                os.system(f'start {url}')
            elif system == "Darwin":  # macOS
                os.system(f'open {url}')
            elif system == "Linux":
                os.system(f'xdg-open {url}')
            print(f"✅ Browser opened using system command at {url}")
        except Exception as e2:
            print(f"❌ Failed to open browser: {e2}")


if __name__ == '__main__':
    setup_app()

    # Create and start browser opening thread
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()

    print("🚀 Starting web server...")
    app.run(debug=True, use_reloader=False)  # Added use_reloader=False to prevent double browser opening
