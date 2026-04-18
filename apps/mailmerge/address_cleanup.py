import csv
import argparse
import re
import os
import tempfile
import shutil

# Common USPS street suffix abbreviations
STREET_SUFFIXES = {
    r'\bSTREET\b': 'ST',
    r'\bAVENUE\b': 'AVE',
    r'\bBOULEVARD\b': 'BLVD',
    r'\bROAD\b': 'RD',
    r'\bDRIVE\b': 'DR',
    r'\bLANE\b': 'LN',
    r'\bCOURT\b': 'CT',
    r'\bPLACE\b': 'PL',
    r'\bSQUARE\b': 'SQ',
    r'\bTRAIL\b': 'TR',
    r'\bPARKWAY\b': 'PKWY',
    r'\bCIRCLE\b': 'CIR',
    r'\bHIGHWAY\b': 'HWY'
}

# Common directional abbreviations
DIRECTIONALS = {
    r'\bNORTH\b': 'N',
    r'\bSOUTH\b': 'S',
    r'\bEAST\b': 'E',
    r'\bWEST\b': 'W',
    r'\bNORTHEAST\b': 'NE',
    r'\bNORTHWEST\b': 'NW',
    r'\bSOUTHEAST\b': 'SE',
    r'\bSOUTHWEST\b': 'SW'
}

def clean_street(street):
    if not street:
        return ""
    # Uppercase and strip whitespace
    street = street.upper().strip()
    # Remove multiple spaces
    street = re.sub(r'\s+', ' ', street)
    # Remove punctuation (periods, commas)
    street = re.sub(r'[.,]', '', street)
    
    # Apply standard USPS abbreviations
    for pattern, replacement in DIRECTIONALS.items():
        street = re.sub(pattern, replacement, street)
    for pattern, replacement in STREET_SUFFIXES.items():
        street = re.sub(pattern, replacement, street)
        
    return street

def clean_zip(zip_code):
    if not zip_code:
        return ""
    # Strip whitespace and non-alphanumeric characters except hyphen
    zip_code = re.sub(r'[^\d-]', '', str(zip_code)).strip()
    
    # If it's a 9-digit zip without a hyphen, add it
    if len(zip_code) == 9 and '-' not in zip_code:
        zip_code = f"{zip_code[:5]}-{zip_code[5:]}"
        
    # Remove trailing hyphen if +4 is missing
    if zip_code.endswith('-'):
        zip_code = zip_code[:-1]
        
    # Pad 4-digit zips with leading zero (common in Northeast US)
    if len(zip_code) == 4:
        zip_code = f"0{zip_code}"
        
    return zip_code

def process_csv(filepath):
    """
    Reads the CSV, cleans address fields, and safely overwrites the original file.
    """
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found.")
        return

    # Create a temporary file to write to, preventing data loss if the script crashes mid-write
    fd, temp_path = tempfile.mkstemp(suffix='.csv', text=True)
    
    try:
        with open(filepath, mode='r', encoding='utf-8') as infile, \
             os.fdopen(fd, mode='w', encoding='utf-8', newline='') as outfile:
            
            reader = csv.DictReader(infile)
            fieldnames = reader.fieldnames
            
            if not fieldnames:
                print("Error: CSV file is empty or missing headers.")
                return
                
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            
            processed_count = 0
            for row in reader:
                # 1. Clean primary and secondary street
                if 'primary street' in row:
                    row['primary street'] = clean_street(row['primary street'])
                if 'sec-primary street' in row:
                    row['sec-primary street'] = clean_street(row['sec-primary street'])
                
                # 2. Clean city and state (uppercase, strip whitespace)
                if 'primary city' in row:
                    row['primary city'] = row['primary city'].upper().strip()
                if 'primary state' in row:
                    row['primary state'] = row['primary state'].upper().strip()[:2] # Force 2-letter state
                
                # 3. Clean ZIP code
                if 'primary zip' in row:
                    row['primary zip'] = clean_zip(row['primary zip'])
                    
                # 4. Rebuild the combined city-state-zip field
                if all(k in row for k in ('primary city', 'primary state', 'primary zip', 'city-state-zip')):
                    city = row['primary city']
                    state = row['primary state']
                    zip_code = row['primary zip']
                    if city or state or zip_code:
                        row['city-state-zip'] = f"{city} {state} {zip_code}".strip()
                        # Remove double spaces if a field was missing
                        row['city-state-zip'] = re.sub(r'\s+', ' ', row['city-state-zip'])

                writer.writerow(row)
                processed_count += 1
                
        # Safely replace the original file with the cleaned temporary file
        shutil.move(temp_path, filepath)
        print(f"Successfully cleaned {processed_count} records in '{filepath}'.")
        
    except Exception as e:
        os.remove(temp_path) # Clean up temp file on failure
        print(f"An error occurred during processing: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean and standardize addresses in a mailing CSV.")
    parser.add_argument("csv_file", help="Path to the CSV file to clean")
    args = parser.parse_args()
    
    process_csv(args.csv_file)
