import json
import os
import requests
import openai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Constants for CORS headers
CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization'
}

def lambda_handler(event, context):
   
    try:
        # Parse the request body
        body = json.loads(event.get('body', '{}'))
        location = body.get('location')
        place_name = body.get('place_name')

        # Determine which function to call based on the input
        if place_name:
            result = get_hospitals_by_place(place_name)
        elif location:
            result = handle_location_request(location)
        else:
            return format_response(
                status_code=400,
                body={"error": "Invalid request parameters. Provide 'location' with latitude and longitude or 'place_name'."},
                headers=CORS_HEADERS
            )

        # Return the result
        return format_response(
            status_code=200,
            body=result,
            headers=CORS_HEADERS
        )

    except Exception as e:
        # Handle unexpected errors
        return format_response(
            status_code=500,
            body={"error": f"An unexpected error occurred: {str(e)}"},
            headers=CORS_HEADERS
        )

def handle_location_request(location):
   
    try:
        google_api_key, open_api_key = get_api_keys()

        # Construct the URL for Google Places API
        places_url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={location}&radius=500&type=hospital&key={google_api_key}"
        places = fetch_data(places_url)
        if not places.get('results'):
            return {"error": "No hospitals found within the specified radius."}

        # Get details of up to 5 hospitals and sort by rating
        hospital_details = [get_hospital_details(place.get('place_id')) for place in places.get('results', [])[:5] if place.get('place_id')]
        hospital_details = sorted(filter(None, hospital_details), key=lambda x: x.get('rating', 0), reverse=True)
        summary = summarize_hospitals(open_api_key, hospital_details)

        return {"hospital_details": hospital_details, "summary": summary}

    except Exception as e:
        return {"error": str(e)}

def get_hospitals_by_place(place_name):
    try:
        google_api_key, open_api_key = get_api_keys()

        # Get latitude and longitude from Google Geocoding API
        geocode_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={place_name}&key={google_api_key}"
        location = fetch_data(geocode_url)
        if not location.get('results'):
            return {"error": "Failed to get location from Google Geocoding API"}

        lat, lng = location['results'][0]['geometry']['location']['lat'], location['results'][0]['geometry']['location']['lng']
        places_url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lng}&radius=500&type=hospital&key={google_api_key}"
        hospitals = fetch_data(places_url)

        if not hospitals.get('results'):
            return {"error": "No hospitals found near the specified location"}

        # Get details of up to 5 hospitals and sort by rating
        hospital_details = [get_hospital_details(hospital.get('place_id')) for hospital in hospitals['results'][:5] if hospital.get('place_id')]
        hospital_details = sorted(filter(None, hospital_details), key=lambda x: x.get('rating', 0), reverse=True)
        summary = summarize_hospitals(open_api_key, hospital_details)

        return {"hospital_details": hospital_details, "summary": summary}

    except Exception as e:
        return {"error": str(e)}

def get_hospital_details(place_id):
    try:
        google_api_key = os.getenv('GOOGLE_API_KEY')
        url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=name,formatted_address,formatted_phone_number,rating&key={google_api_key}"
        result = fetch_data(url)
        return result.get('result', {}) if result else {}
    except requests.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Request failed: {str(e)}"}
    
def summarize_hospitals(openai_api_key, hospital_details):
    openai.api_key = openai_api_key

    summary_text = (
    "Here is the list of the top-rated hospitals:\n\n" +
    '\n\n'.join(
        f"Hospital Name: {hospital.get('name', 'Unknown')}\n"
        f"Location: {hospital.get('formatted_address', 'Address not available')}\n"
        f"Rating: {hospital.get('rating', 'Rating not available')}\n"
        f"Contact: {hospital.get('formatted_phone_number', 'Contact not available')}\n"
        for hospital in hospital_details[:5]
    )
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a hospital finder. Format the following hospital details into a point-wise list. "
                        "Each hospital's details should be presented in the following format:\n\n"
                        "Hospital Name: Example Hospital\n"
                        "Location: 123 Example St, Example City, EX 12345\n"
                        "Rating: 4.5\n"
                        "Contact: (555) 123-4567\n\n"
                        "Ensure each hospital's details are separated by a blank line.\n\n"
                        "Apply this format to each hospital's details provided below.\n\n"
                        "Include the heading 'Here is the list of the top-rated hospitals:' before the details."
                    )
                },
                {"role": "user", "content": summary_text}
            ]
        )
        # Extracting the summary from the response
        summary = response.choices[0].message['content'].strip()
        return summary
    except openai.OpenAIError as e:
        return f"Error summarizing hospitals: {str(e)}"
    except Exception as e:
        return f"Error summarizing hospitals: {str(e)}"

def get_api_keys():
    google_api_key = os.getenv('GOOGLE_API_KEY')
    open_api_key = os.getenv('OPENAI_API_KEY')
    if not google_api_key or not open_api_key:
        raise ValueError("API keys are not set properly.")
    return google_api_key, open_api_key

def fetch_data(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise Exception(f"Request failed: {str(e)}")

def format_response(status_code, body, headers=None):
    response = {
        'statusCode': status_code,
        'body': json.dumps(body)
    }
    if headers:
        response['headers'] = headers
    return response
