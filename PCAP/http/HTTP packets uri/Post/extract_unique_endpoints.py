#!/usr/bin/env python3
import argparse
import re
from urllib.parse import urlsplit, urlunsplit

def is_static_segment(segment):
    """
    Heuristic to determine if a URL path segment is part of the base API.
    """
    if not segment:
        return False
        
    # 1. Drop pure numbers (e.g., Train numbers '82902', Dates '20250620')
    if segment.isdigit():
        return False
        
    # 2. Drop short uppercase strings (e.g., Station codes 'MMCT', Class 'CC', Flags 'Y')
    if segment.isupper() and len(segment) <= 4:
        return False
        
    # 3. Drop Hexadecimal strings or long Alphanumeric IDs (e.g., 'f3109944', 'f32759a7')
    # If it contains both letters and numbers, and is 7 characters or longer, 
    # it is almost certainly a dynamic token. (We use >= 7 to safely keep 'mapps1')
    has_digit = any(c.isdigit() for c in segment)
    has_alpha = any(c.isalpha() for c in segment)
    
    if has_digit and has_alpha and len(segment) >= 7:
        return False
        
    # 4. Drop UUIDs or pure hex strings of length 6+ (just to be completely safe)
    if re.match(r'^[0-9a-fA-F]{6,}$', segment):
        return False
        
    return True

def extract_base_url(raw_url):
    if not raw_url.startswith('http'):
        raw_url = 'http://' + raw_url
        
    parsed = urlsplit(raw_url.strip())
    path_segments = parsed.path.split('/')
    
    # Filter the segments using our updated heuristic
    cleaned_segments = [seg for seg in path_segments if is_static_segment(seg)]
    cleaned_path = '/'.join(cleaned_segments)
    
    if parsed.path.endswith('/') and cleaned_segments:
        cleaned_path += '/'
        
    base_url = urlunsplit((parsed.scheme, parsed.netloc, cleaned_path, '', ''))
    return base_url

def main():
    parser = argparse.ArgumentParser(description="Extract unique base API endpoints.")
    parser.add_argument("-i", "--input", required=True, help="Input text file")
    parser.add_argument("-o", "--output", required=True, help="Output text file")
    
    args = parser.parse_args()
    unique_endpoints = set()
    
    print(f"Reading URLs from {args.input}...")
    try:
        with open(args.input, 'r') as infile:
            for line in infile:
                line = line.strip()
                if line:
                    base_endpoint = extract_base_url(line)
                    unique_endpoints.add(base_endpoint)
                    
    except FileNotFoundError:
        print(f"Error: Could not find input file '{args.input}'")
        return
        
    sorted_endpoints = sorted(list(unique_endpoints))
    
    print(f"Found {len(sorted_endpoints)} unique base endpoints. Saving to {args.output}...")
    with open(args.output, 'w') as outfile:
        for endpoint in sorted_endpoints:
            outfile.write(endpoint + '\n')
            
    print("Done!")

if __name__ == '__main__':
    main()