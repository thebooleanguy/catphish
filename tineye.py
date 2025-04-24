import os
import instaloader
import requests
from time import sleep
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options

class InstagramScraper:
    def __init__(self):
        self.options = Options()
        # Remove headless argument to allow visual interaction
        # self.options.add_argument("--headless")  # Uncomment for headless mode
        self.driver = webdriver.Firefox(options=self.options)

        # Initialize Instaloader
        self.instaloader = instaloader.Instaloader()

    def get_profile_picture(self, profile_url):
        # Get the username from the URL
        username = profile_url.split('/')[-2]

        # Download profile using Instaloader
        profile = instaloader.Profile.from_username(self.instaloader.context, username)
        profile_pic_url = profile.profile_pic_url
        print(f"Profile picture URL: {profile_pic_url}")
        return profile_pic_url

    def download_image(self, img_url, save_path):
        # Download image
        response = requests.get(img_url)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            print(f"Image downloaded at: {save_path}")
        else:
            print("Failed to download image.")

    def reverse_image_search_tineye(self, img_path):
        # Go to TinEye reverse image search
        self.driver.get('https://www.tineye.com/')
        sleep(2)

        # Locate the upload button and upload the image
        upload_button = self.driver.find_element(By.XPATH, '//*[@id="upload"]')
        upload_button.send_keys(img_path)
        sleep(5)

        # Wait for results to load
        results_section = self.driver.find_element(By.XPATH, '//*[@id="results"]/div[2]')
        print("Results fetched from TinEye:")
        print(results_section.text)  # You can extract and print relevant result information

    def close(self):
        self.driver.quit()


# Usage example
scraper = InstagramScraper()

# Replace with the Instagram profile URL you want to test
profile_url = 'https://www.instagram.com/tarindu_sandes/'  # Example of a public profile
img_url = scraper.get_profile_picture(profile_url)

# Download the image
save_path = 'profile_pic.jpg'  # Save path for the profile picture
scraper.download_image(img_url, save_path)

# Perform TinEye reverse image search
scraper.reverse_image_search_tineye(save_path)

# Close the browser
scraper.close()

