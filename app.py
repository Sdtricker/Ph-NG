from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
import requests
from urllib.parse import urlparse, parse_qs
import re

app = Flask(__name__)

BASE_URL = "https://calltracer.in"
HEADERS = {
    "Host": "calltracer.in",
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Content-Type": "application/x-www-form-urlencoded"
}


def fetch_page(number: str):
    payload = {"country": "IN", "q": number}
    resp = requests.post(BASE_URL, headers=HEADERS, data=payload, timeout=25)
    resp.raise_for_status()
    return resp.text


def parse_table(soup: BeautifulSoup):
    table = soup.find("table", class_="trace-details") or soup.find("table")
    if not table:
        return {}
    details = {}
    last_key = None
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) >= 2:
            key = cells[0].get_text(strip=True)
            value = cells[1].get_text(" ", strip=True)
            if key in details:
                if not isinstance(details[key], list):
                    details[key] = [details[key]]
                details[key].append(value)
            else:
                details[key] = value
            last_key = key
        elif len(cells) == 1 and last_key:
            val = cells[0].get_text(" ", strip=True)
            if isinstance(details[last_key], list):
                details[last_key].append(val)
            else:
                details[last_key] = [details[last_key], val]
    return details


def extract_map_iframe(soup: BeautifulSoup):
    iframe = soup.find("iframe", id="map")
    if iframe and iframe.get("src"):
        return iframe["src"]
    for tag in soup.find_all("iframe"):
        src = tag.get("src", "")
        if "google.com/maps" in src:
            return src
    return None


def extract_lat_lng(iframe_src: str):
    if not iframe_src:
        return None
    # try to find lat/lng pattern
    match = re.search(r"([0-9]+\.[0-9]+)[, ]+([0-9]+\.[0-9]+)", iframe_src)
    if match:
        return {"lat": float(match.group(1)), "lng": float(match.group(2))}
    return None


@app.route("/", methods=["GET", "POST"])
def index():
    number = request.args.get("number") or request.args.get("q")
    if not number and request.is_json:
        data = request.get_json(silent=True) or {}
        number = data.get("number") or data.get("q")

    if not number:
        return jsonify({
            "success": False,
            "error": "Missing 'number' parameter made by @NGYT777GG (use ?number=... or POST JSON)"
        }), 400

    include_raw = (request.args.get("raw") == "1")

    try:
        html = fetch_page(number)
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to fetch: {str(e)}"
        }), 500

    soup = BeautifulSoup(html, "html.parser")
    fields = parse_table(soup)
    iframe_src = extract_map_iframe(soup)
    coords = extract_lat_lng(iframe_src)

    response = {
        "success": True,
        "phone_number": number,
        "source": BASE_URL,
        "fields": fields,
        "iframe_src": iframe_src,
        "map": coords
    }

    if include_raw or not fields:
        response["_raw_html"] = html

    return jsonify(response)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
