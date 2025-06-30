import requests
import json
import os
from flask_session import Session
from dotenv import load_dotenv # Import load_dotenv, not get_key
from flask import Flask, render_template, request, session, redirect, url_for, send_file
from datetime import datetime

# --- Load Environment Variables ---
# Load variables from .env file into the environment
load_dotenv()

app = Flask(__name__)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


def send_api_request(search_value:str):
    print("sent another request")
    # Use os.getenv to read the loaded environment variable
    key = os.getenv("weather_api")
    if not key:
        print("Error: weather_api key not found in environment variables.")
        return "Error" # Handle missing API key gracefully

    r = requests.get(f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{search_value}/next7days?unitGroup=metric&elements=datetime%2Ctempmax%2Ctempmin%2Chumidity&include=days&key={key}&contentType=json")
    if r.status_code == 400:
        print(f"Error 400 from API for {search_value}. Response: {r.text}")
        return "Error"
    elif r.status_code != 200:
        print(f"Error {r.status_code} from API for {search_value}. Response: {r.text}")
        return "Error" # Handle other non-200 errors

    try:
        j = r.json()
        save_weather_data(search_value, j)
        return j
    except json.JSONDecodeError:
        print(f"Error decoding JSON response for {search_value}. Response: {r.text}")
        return "Error"


def save_weather_data(city_name: str, data: dict):
    """Save the weather data to a JSON file based on the date and city name."""
    try:
        first_day = data.get("days", [])[0]  # Get the first day of the forecast
        date = first_day.get("datetime", datetime.now().strftime("%Y-%m-%d"))  # Use the date or current date if missing
    except (IndexError, TypeError, AttributeError) as e:
        print(f"Error extracting date from weather data for {city_name}: {e}")
        # Fallback to current date if data structure is unexpected
        date = datetime.now().strftime("%Y-%m-%d")

    # Sanitize city_name to prevent directory traversal or invalid filenames
    safe_city_name = "".join(c for c in city_name if c.isalnum() or c in (' ', '-')).rstrip()
    if not safe_city_name:
        safe_city_name = "unknown_city" # Fallback if city name is unusable

    filename = f"{safe_city_name}-{date}.json"
    queries_dir = 'queries'
    os.makedirs(queries_dir, exist_ok=True)

    file_path = os.path.join(queries_dir, filename)

    # Use 'w' to overwrite/create file, 'a' (append) might lead to invalid JSON over time
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Weather data for {city_name} on {date} saved to {file_path}")
    except IOError as e:
        print(f"Error writing weather data to {file_path}: {e}")


@app.route("/results")
def get_results():
    country_name = request.args.get('Country_Name', '').strip() # Add default and strip whitespace
    if not country_name: # Check if empty after stripping
        # Maybe flash a message here?
        return redirect(url_for("home"))

    # Check session first (good practice)
    if country_name in session:
         print(f"Cache hit for {country_name}")
         returned_dict = session[country_name]
         # Make sure data is not None or empty before rendering
         if returned_dict:
             return render_template('weather_for_country.html',
                                    Title=country_name,
                                    Start_Time=list(returned_dict.items())[0][0],
                                    End_Time=list(returned_dict.items())[-1][0],
                                    Week_Forcast=returned_dict.items())
         else:
             # If session data is invalid, remove it and try fetching again
             del session[country_name]

    # If not in session or session data was invalid, fetch from API
    print(f"Cache miss for {country_name}, fetching from API...")
    json_val = send_api_request(country_name)

    if json_val == "Error" or not isinstance(json_val, dict) or "days" not in json_val:
        # Add user feedback here (e.g., using flash messages)
        print(f"Failed to get valid data for {country_name}")
        return redirect(url_for("home")) # Redirect on error

    returned_dict = {}
    try:
        for i in json_val["days"]:
            returned_dict[i['datetime']] = (i.get('tempmax', 'N/A'), i.get('tempmin', 'N/A'), i.get('humidity', 'N/A'))
    except (TypeError, KeyError, AttributeError) as e:
         print(f"Error processing API response structure for {country_name}: {e}")
         # Redirect or show error page
         return redirect(url_for("home"))


    if not returned_dict: # Check if processing resulted in an empty dict
        print(f"Processed dictionary is empty for {country_name}")
        return redirect(url_for("home"))

    session[country_name] = returned_dict
    return render_template('weather_for_country.html',
                           Title=country_name,
                           Start_Time=list(returned_dict.items())[0][0],
                           End_Time=list(returned_dict.items())[-1][0],
                           Week_Forcast=returned_dict.items())


@app.route("/")
def home():
    # ---- Get Background Color ----
    # Provide a default color ('white') if BG_COLOR is not set in .env
    default_color = 'white'
    background_color = os.getenv('BG_COLOR', default_color)
    # -----------------------------

    # Note: cur_ip = "0.0.0.0" is generally not useful here.
    # If you need the base URL for JavaScript, consider constructing it:
    # base_url = request.url_root  # e.g., "http://127.0.0.1:5000/"

    return render_template('base.html',
                           title="Weather Forecast", # Cleaner title
                           # Pass the retrieved background color to the template
                           bg_color=background_color)
                           # If needed for JS: base_url=base_url)


@app.route("/history")
def history():
    query_files = []
    queries_dir = 'queries'
    if os.path.exists(queries_dir):
        try:
            # Filter out potential non-files (like subdirectories if any)
            files = [f for f in os.listdir(queries_dir) if os.path.isfile(os.path.join(queries_dir, f))]
            # Sort files by modification time (most recent first)
            query_files = sorted(files, key=lambda x: os.path.getmtime(os.path.join(queries_dir, x)), reverse=True)
        except OSError as e:
            print(f"Error accessing queries directory {queries_dir}: {e}")
            # Handle error, maybe show an empty list or an error message

    return render_template('history.html', title="Query History", query_files=query_files)


@app.route("/download/<path:filename>") # Use path converter for flexibility
def download_file(filename):
    queries_dir = 'queries'
    # Use os.path.abspath and check if the path starts with the queries directory
    # This provides better security against directory traversal.
    base_dir = os.path.abspath(queries_dir)
    file_path = os.path.abspath(os.path.join(base_dir, filename))

    if not file_path.startswith(base_dir):
        # Security: Prevent access outside of the intended directory
        print(f"Attempt to access file outside designated directory: {filename}")
        return redirect(url_for('history')) # Or return 404/403

    if os.path.exists(file_path) and os.path.isfile(file_path):
        try:
            return send_file(file_path, as_attachment=True)
        except Exception as e:
            print(f"Error sending file {filename}: {e}")
            # Handle error appropriately
            return redirect(url_for('history')) # Fallback redirect
    else:
        print(f"Download request for non-existent file: {filename}")
        return redirect(url_for('history')) # Redirect if file doesn't exist


if __name__ == "__main__":
    # Consider adding host='0.0.0.0' to make it accessible on your network
    # and debug=True for development (remove debug=True for production)
    app.run(port=9090, debug=True) # Example port, debug=True recommended for dev
