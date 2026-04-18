import requests
import os
import sys
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

CLIENT_ID = os.environ.get('PLANNING_CENTER_CLIENT_ID')
SECRET = os.environ.get('PLANNING_CENTER_SECRET')
BASE_URL = 'https://api.planningcenteronline.com/people/v2'

def get_mailing_lists(target_category="Mailing"):
    """
    Fetches lists from PCO filtered by category and returns a list of dictionaries with id and name.
    """
    if not CLIENT_ID or not SECRET:
        # Print errors to stderr so stdout remains valid JSON
        print(json.dumps({"error": "Missing credentials in .env file"}), file=sys.stderr)
        sys.exit(1)

    url = f"{BASE_URL}/lists?include=category"
    mailing_lists = []
    
    while url:
        response = requests.get(url, auth=(CLIENT_ID, SECRET))
        
        if response.status_code != 200:
            print(json.dumps({
                "error": f"API returned status code {response.status_code}", 
                "details": response.text
            }), file=sys.stderr)
            sys.exit(1)
            
        data = response.json()
        
        # Build a dictionary to map Category IDs to Category Names
        categories = {}
        for included_item in data.get('included', []):
            if included_item.get('type') == 'ListCategory':
                categories[included_item['id']] = included_item['attributes']['name']
                
        # Extract ID and Name for each list
        for pco_list in data.get('data', []):
            list_id = pco_list['id']
            list_name = pco_list['attributes']['name']
            
            relationships = pco_list.get('relationships', {})
            category_data = relationships.get('category', {}).get('data')
            
            if category_data:
                category_id = category_data.get('id')
                category_name = categories.get(category_id, "")
                
                # Case-insensitive match
                if category_name.lower() == target_category.lower():
                    mailing_lists.append({
                        "id": list_id,
                        "name": list_name
                    })
                    
        # Handle pagination
        url = data.get('links', {}).get('next')
        
    return mailing_lists

if __name__ == "__main__":
    lists = get_mailing_lists("Mailing")
    
    # Output the final result as a formatted JSON string
    print(json.dumps(lists, indent=2))
