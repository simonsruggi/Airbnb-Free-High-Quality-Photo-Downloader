import os
import json
import random
import requests
from bs4 import BeautifulSoup


class AirbnbScraper:
    def __init__(self, destination_folder):
        self.link_photos = []
        self.destination_folder = destination_folder
        if not os.path.exists(destination_folder):
            os.makedirs(destination_folder)

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
            soup = BeautifulSoup(response.text, 'html.parser')
            script_tags = soup.find('script', id='data-deferred-state').text
            data = json.loads(script_tags)[
                'niobeMinimalClientData'][0][1]['data']['presentation']
            self.traverse_dict(data)
        except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError) as e:
            print(f"Failed to get image links due to {e}")

    def download_image(self, url):
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

    def scrape_airbnb(self, airbnb_url):
        num_downloaded = 0
        try:
            if 'https://www.airbnb.com/rooms/' in airbnb_url or 'https://airbnb.com/' in airbnb_url:
                self.get_image_links(airbnb_url)
            elif len(airbnb_url) == 18:
                airbnb_url = 'https://www.airbnb.com/rooms/' + airbnb_url
                self.get_image_links(airbnb_url)
            else:
                print('Invalid room number provided')
                return
        except TypeError as e:
            print(f"Failed to scrape Airbnb due to {e}")
            return

        print('Found {} image urls'.format(len(self.link_photos)))
        if self.link_photos:
            for url in self.link_photos:
                if self.download_image(url):
                    num_downloaded += 1

        print('Successfully downloaded {} photos and saved them in directory: {}'.format(
            num_downloaded, os.path.abspath(self.destination_folder)))


def main():
    print('Please input your airbnb listing URL or room number (room number must have 18 chars)')
    airbnb_url = input()
    destination_folder = 'airbnb_home_photos' + str(random.randint(0, 1000))
    scraper = AirbnbScraper(destination_folder)
    scraper.scrape_airbnb(airbnb_url)


if __name__ == "__main__":
    main()
