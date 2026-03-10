import re
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

def extract_address_from_url(url):
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.split('/') if p]

    # Try to find the part that looks most like an address
    # Usually it's the longest string with hyphens or numbers
    address_part = ""
    for part in reversed(path_parts):
        if re.search(r'\d', part) and '-' in part:
            address_part = part
            break

    if not address_part and path_parts:
        address_part = path_parts[-1]

    # Clean up the address part
    # Remove some common trailing IDs like _zpid or -12345
    address_part = re.sub(r'_[a-z0-9]+$', '', address_part)
    # Replaces dashes with spaces
    address = address_part.replace('-', ' ')

    return address.title()

def scrape_url(url: str):
    address = extract_address_from_url(url)
    start_time = "09:00"
    end_time = "22:00"

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        # Try to fetch, timeout quickly if blocked or slow
        response = requests.get(url, headers=headers, timeout=5)

        # Some sites block requests, so if we don't get 200, we fallback
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            text = soup.get_text(separator=' ', strip=True)

            # Simple regex to find times
            pattern = r'(\d{1,2}(?::\d{2})?\s*(?:AM|PM|A\.M\.|P\.M\.|am|pm|a\.m\.|p\.m\.)?)\s*(?:-|to|–|and)\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM|A\.M\.|P\.M\.|am|pm|a\.m\.|p\.m\.)?)'
            matches = re.findall(pattern, text, re.IGNORECASE)

            if matches:
                def parse_time(t_str):
                    t_str = t_str.upper()
                    is_pm = 'PM' in t_str or 'P.M.' in t_str
                    is_am = 'AM' in t_str or 'A.M.' in t_str
                    t_str = re.sub(r'[A-Z\.]', '', t_str).strip()
                    if ':' in t_str:
                        parts = t_str.split(':')
                        h, m = int(parts[0]), int(parts[1])
                    else:
                        h, m = int(t_str), 0
                    if is_pm and h < 12: h += 12
                    elif is_am and h == 12: h = 0
                    return f"{h:02d}:{m:02d}"

                # Use the first reasonable time match we find
                for start_str, end_str in matches:
                    try:
                        if ('PM' in end_str.upper() or 'P.M.' in end_str.upper()) and not ('AM' in start_str.upper() or 'PM' in start_str.upper()):
                            start_str += ' PM'

                        s_time = parse_time(start_str)
                        e_time = parse_time(end_str)

                        # basic sanity check
                        if s_time < e_time:
                            start_time = s_time
                            end_time = e_time
                            break
                    except Exception as e:
                        continue
    except Exception as e:
        print(f"Scrape failed: {e}")

    return {"address": address, "start_time": start_time, "end_time": end_time}
