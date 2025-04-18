import os
import json
import random
import requests
from bs4 import BeautifulSoup
import sys
import re


class AirbnbScraper:
    def __init__(self, destination_folder):
        self.link_photos = []
        self.destination_folder = destination_folder

    def create_destination_folder(self):
        if not os.path.exists(self.destination_folder):
            os.makedirs(self.destination_folder)
            return True
        return False

    def traverse_dict(self, dictionary):
        for key, value in dictionary.items():
            if isinstance(value, dict):
                self.traverse_dict(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        self.traverse_dict(item)
            elif key == 'baseUrl' and 'original' in value and value not in self.link_photos:
                self.link_photos.append(value)

    def get_image_links(self, url):
        headers = {
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7'
        }
        try:
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                print(f"Failed to access URL. Status code: {response.status_code}")
                return False
                
            soup = BeautifulSoup(response.text, 'html.parser')
            script_tags = soup.find('script', id='data-deferred-state-0')
            if not script_tags:
                print("Could not find required data in the page. This may not be a valid Airbnb listing.")
                return False
                
            script_tags = script_tags.text
            data = json.loads(script_tags)[
                'niobeMinimalClientData'][0][1]['data']['presentation']
            self.traverse_dict(data)
            return True
        except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"Failed to get image links due to {e}")
            return False

    def download_image(self, url):
        url = url.replace('/im/pictures', '/pictures')
        url = url.split("?")[0]
        image_name = url.split("/")[-1]
        try:
            r = requests.get(url, stream=True)
        except requests.exceptions.RequestException as e:
            print(f"Failed to connect to url {url}, due to {e}")
            return False
        if r.status_code == 200:
            r.raw.decode_content = True
            try:
                self.create_destination_folder()
                with open(os.path.join(self.destination_folder, image_name), 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            except OSError as e:
                print(f"Failed to save image {image_name}, due to {e}")
                return False
            print('Image successfully Downloaded: ', image_name)
            return True
        else:
            print('Image Couldn\'t be retreived')
            return False

    def extract_room_id(self, url):
        standard_pattern = r'airbnb\.com/rooms/(\d+)'
        direct_pattern = r'^(\d{8}|\d{18})$'
        
        match = re.search(standard_pattern, url, re.IGNORECASE)
        if match:
            return match.group(1)
        
        match = re.search(direct_pattern, url)
        if match:
            return match.group(1)
        
        try:
            headers = {
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
            }
            response = requests.get(url, headers=headers, allow_redirects=True)
            
            if response.status_code != 200:
                print(f"Failed to access URL. Status code: {response.status_code}")
                return None
                
            final_url = response.url
            match = re.search(standard_pattern, final_url, re.IGNORECASE)
            if match:
                return match.group(1)
                
            soup = BeautifulSoup(response.text, 'html.parser')
            meta_tags = soup.find_all('meta')
            for tag in meta_tags:
                if tag.get('property') == 'og:url':
                    content = tag.get('content', '')
                    match = re.search(standard_pattern, content, re.IGNORECASE)
                    if match:
                        return match.group(1)
        except Exception as e:
            print(f"Failed to extract room ID from custom URL: {e}")
        
        return None

    def scrape_airbnb(self, airbnb_url):
        num_downloaded = 0
        
        if not airbnb_url or not airbnb_url.strip():
            print("Error: No URL provided")
            return
            
        try:
            if 'https://www.airbnb.com/rooms/' in airbnb_url or 'https://airbnb.com/rooms/' in airbnb_url:
                if not self.get_image_links(airbnb_url):
                    print("Failed to process the Airbnb URL. Please verify the URL is correct.")
                    return
            else:
                room_id = self.extract_room_id(airbnb_url)
                if room_id:
                    standard_url = f'https://www.airbnb.com/rooms/{room_id}'
                    print(f"Extracted room ID: {room_id}")
                    if not self.get_image_links(standard_url):
                        print("Failed to process the Airbnb listing. Please verify the URL is correct.")
                        return
                else:
                    print(f"Trying to scrape URL directly: {airbnb_url}")
                    if not self.get_image_links(airbnb_url):
                        print("Invalid URL. Could not find an Airbnb listing.")
                        return
        except Exception as e:
            print(f"Failed to scrape Airbnb due to: {e}")
            return

        if not self.link_photos:
            print("No images found. The URL may not be a valid Airbnb listing.")
            return
            
        print(f'Found {len(self.link_photos)} image URLs')
        self.create_destination_folder()
        print(f'Saving photos to: {os.path.abspath(self.destination_folder)}')
        
        for url in self.link_photos:
            if self.download_image(url):
                num_downloaded += 1

        print(f'Successfully downloaded {num_downloaded} photos and saved them in directory: {os.path.abspath(self.destination_folder)}')


def main():
    print('Please input your Airbnb listing URL or room number:')
    print('Supported formats: room number, standard Airbnb URL, or custom URLs that redirect to Airbnb listings')
    airbnb_url = input()
    destination_folder = 'airbnb_home_photos' + str(random.randint(0, 1000))
    scraper = AirbnbScraper(destination_folder)
    scraper.scrape_airbnb(airbnb_url)


if __name__ == "__main__":
    main()
