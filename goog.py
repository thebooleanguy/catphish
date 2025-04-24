import instaloader
from selenium import webdriver
from selenium.webdriver.common.by import By
from time import sleep
import os

# --- Step 1: Download profile pic using instaloader ---
def download_profile_pic(username):
    loader = instaloader.Instaloader(download_pictures=True, download_videos=False,
                                     download_video_thumbnails=False, save_metadata=False,
                                     post_metadata_txt_pattern='', compress_json=False)
    loader.download_profile(username, profile_pic_only=True)

    # Locate the downloaded profile picture
    folder = os.path.join(os.getcwd(), username)
    for file in os.listdir(folder):
        if file.endswith('.jpg'):
            return os.path.join(folder, file)

# Example username (public IG profile)
ig_username = "dani_daniels_x57"  # Replace with the profile you want
image_path = download_profile_pic(ig_username)

# --- Step 2: Upload profile pic URL to Google Reverse Image ---
driver = webdriver.Firefox()  # Non-headless Firefox

driver.get("https://images.google.com")
sleep(8)

# Click the camera icon to do image search
search_by_image_btn = driver.find_element(By.XPATH, "/html/body/div[1]/div[3]/form/div[1]/div[1]/div[1]/div[1]/div[3]/div[3]")
search_by_image_btn.click()
sleep(5)

# Click on the "Paste image link" tab (this is auto-selected usually)
# If needed, add a tab switcher here (XPath if tabs are detected)

# Upload via URL (workaround to get a URL for local file: use file:///path)
# Google does not support local file upload via URL input
# So we need to serve it or use another method. Better to automate file upload.

# Alternative: simulate file upload (bypassing URL input)
# Instead of image URL input, upload the image
# Google doesn't allow URL uploads for local files, so let's do this:
# 1. Click "Upload an image" tab
# 2. Upload the file via <input type="file">

# Locate file input (hidden input field)
upload_input = driver.find_element(By.XPATH, "//input[@type='file']")
upload_input.send_keys(image_path)
sleep(5)

print("Image uploaded to Google Reverse Image Search!")
print("Profile pic path:", image_path)
print("Browser window is open – check results manually.")

# Done! Keep browser open
# driver.quit()  # Uncomment if you want to auto-close

