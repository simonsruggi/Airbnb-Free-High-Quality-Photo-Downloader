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

    def _extract_presentation_from_data(self, data_obj):
        if isinstance(data_obj, dict):
            if 'presentation' in data_obj:
                return data_obj['presentation']
            for v in data_obj.values():
                found = self._extract_presentation_from_data(v)
                if found is not None:
                    return found
        elif isinstance(data_obj, list):
            for item in data_obj:
                found = self._extract_presentation_from_data(item)
                if found is not None:
                    return found
        return None

    def get_image_links(self, url):
        base_headers = {
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9,it;q=0.8',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'upgrade-insecure-requests': '1'
        }
        candidate_urls = [url]
        if '?' in url:
            candidate_urls.append(url + '&locale=en')
        else:
            candidate_urls.append(url + '?locale=en')

        try:
            found_presentation = None
            last_response_text = ''
            for candidate in candidate_urls:
                response = requests.get(candidate, headers=base_headers, timeout=15)
                if response.status_code != 200:
                    continue

                last_response_text = response.text
                soup = BeautifulSoup(response.text, 'html.parser')
                candidate_scripts = []
                for script_tag in soup.find_all('script'):
                    script_id = script_tag.get('id')
                    if script_id and (script_id.startswith('data-deferred-state') or script_id == 'data-state' or script_id == '__NEXT_DATA__'):
                        candidate_scripts.append(script_tag)
                # broaden: any script containing the key string
                if not candidate_scripts:
                    for s in soup.find_all('script'):
                        text = (s.string or s.text or '').strip()
                        if 'niobeMinimalClientData' in text:
                            candidate_scripts.append(s)

                for s in candidate_scripts:
                    text = s.string or s.text or ''
                    text = text.strip()
                    if not text:
                        continue
                    try:
                        data_json = json.loads(text)
                    except json.JSONDecodeError:
                        continue
                    # find niobe
                    def find_key(obj, target_key):
                        if isinstance(obj, dict):
                            if target_key in obj:
                                return obj[target_key]
                            for v in obj.values():
                                found = find_key(v, target_key)
                                if found is not None:
                                    return found
                        elif isinstance(obj, list):
                            for it in obj:
                                found = find_key(it, target_key)
                                if found is not None:
                                    return found
                        return None
                    niobe = find_key(data_json, 'niobeMinimalClientData')
                    if niobe is None:
                        continue
                    presentation = self._extract_presentation_from_data(niobe)
                    if presentation is not None:
                        found_presentation = presentation
                        break
                if found_presentation is not None:
                    break

            if found_presentation is None:
                # Fallback: regex extraction for baseUrl/original URLs and muscache images
                html = last_response_text
                if not html:
                    print("Could not find required data in the page. This may not be a valid Airbnb listing.")
                    return False
                # Find baseUrl JSON fields
                baseurl_matches = re.findall(r'"baseUrl"\s*:\s*"(https:[^"\\]+)"', html)
                for u in baseurl_matches:
                    if 'original' in u and u not in self.link_photos:
                        self.link_photos.append(u)
                # Find direct muscache images
                img_matches = re.findall(r'https://a0\.muscache\.com/[^"\s>]+\.(?:jpg|jpeg|png)', html, flags=re.IGNORECASE)
                for u in img_matches:
                    # Prefer originals when available; still add if not present
                    if u not in self.link_photos:
                        self.link_photos.append(u)

                if not self.link_photos:
                    print("Could not find required data in the page. This may not be a valid Airbnb listing.")
                    return False

                return True

            self.traverse_dict(found_presentation)
            return True
        except requests.exceptions.RequestException as e:
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
        standard_pattern = r'airbnb\.(?:com|[a-z]{2})/rooms/(\d+)'
        direct_pattern = r'^(\d{8}|\d{18})$'
        og_url_pattern = r'airbnb\.(?:com|[a-z]{2})/rooms/(\d+)'

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
                    match = re.search(og_url_pattern, content, re.IGNORECASE)
                    if match:
                        return match.group(1)

            a_tags = soup.find_all('a', href=True)
            for a in a_tags:
                href = a['href']
                match = re.search(standard_pattern, href, re.IGNORECASE)
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
            if re.search(r'https://(?:www\.)?airbnb\.(?:com|[a-z]{2})/rooms/\d+', airbnb_url):
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
