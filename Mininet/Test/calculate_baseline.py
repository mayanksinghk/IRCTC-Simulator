#!/usr/bin/env python3
import pyshark
import sys
import os

def calculate_baseline(pcap_file):
    if not os.path.exists(pcap_file):
        print(f"[!] Error: File '{pcap_file}' not found.")
        sys.exit(1)

    print(f"[*] Analyzing '{pcap_file}' for HTTP response times...")
    print("[*] Note: This may take a minute for large PCAP files...")

    # We filter specifically for HTTP responses. 
    # Wireshark automatically calculates 'http.time' as the delta from the request.
    try:
        cap = pyshark.FileCapture(pcap_file, display_filter='http.response')
        
        total_time_ms = 0.0
        packet_count = 0

        for pkt in cap:
            try:
                # Extract the 'http.time' field (which is in seconds)
                if hasattr(pkt.http, 'time'):
                    response_time_sec = float(pkt.http.time)
                    total_time_ms += (response_time_sec * 1000.0)
                    packet_count += 1
            except AttributeError:
                # Failsafe if a malformed HTTP packet lacks the time attribute
                continue

        cap.close()

        if packet_count == 0:
            print("[!] No completed HTTP transactions found in this PCAP.")
            print("[!] Ensure the PCAP contains both the GET requests and 200 OK responses.")
            sys.exit(1)

        baseline_ms = total_time_ms / packet_count
        
        print("\n" + "="*40)
        print(f"[*] Processed {packet_count} complete HTTP transactions.")
        print(f"[*] MININET_BASELINE_MS = {baseline_ms:.3f} ms")
        print("="*40 + "\n")
        
        return baseline_ms

    except Exception as e:
        print(f"[!] An error occurred while parsing the PCAP: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Allow passing the PCAP file as a command-line argument
    if len(sys.argv) > 1:
        target_pcap = sys.argv[1]
    else:
        # Default fallback name
        target_pcap = "baseline_test.pcap"
        
    calculate_baseline(target_pcap)