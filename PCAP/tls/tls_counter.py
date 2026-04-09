#! /usr/bin/env python3
import pyshark
import pandas as pd
import matplotlib.pyplot as plt
from collections import Counter
import sys
import os

# The dictionary mapping hex values to a tuple of (Readable Name, TLS Version)
CIPHER_MAP = {
    "0x1301": ("TLS_AES_128_GCM_SHA256", "TLS 1.3"),
    "0x1302": ("TLS_AES_256_GCM_SHA384", "TLS 1.3"),
    "0x1303": ("TLS_CHACHA20_POLY1305_SHA256", "TLS 1.3"),
    "0x1304": ("TLS_AES_128_CCM_SHA256", "TLS 1.3"),
    "0x1305": ("TLS_AES_128_CCM_8_SHA256", "TLS 1.3"),
    "0xc02b": ("TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256", "TLS 1.2"),
    "0xc02c": ("TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384", "TLS 1.2"),
    "0xc02f": ("TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256", "TLS 1.2"),
    "0xc030": ("TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384", "TLS 1.2"),
    "0xcca8": ("TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256", "TLS 1.2"),
    "0xcca9": ("TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256", "TLS 1.2"),
    "0x009e": ("TLS_DHE_RSA_WITH_AES_128_GCM_SHA256", "TLS 1.2"),
    "0x009f": ("TLS_DHE_RSA_WITH_AES_256_GCM_SHA384", "TLS 1.2"),
    "0x009c": ("TLS_RSA_WITH_AES_128_GCM_SHA256", "TLS 1.2"),
    "0x009d": ("TLS_RSA_WITH_AES_256_GCM_SHA384", "TLS 1.2"),
    "0xc009": ("TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA", "TLS 1.2"),
    "0xc00a": ("TLS_ECDHE_ECDSA_WITH_AES_256_CBC_SHA", "TLS 1.2"),
    "0xc013": ("TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA", "TLS 1.2"),
    "0xc014": ("TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA", "TLS 1.2"),
    "0x002f": ("TLS_RSA_WITH_AES_128_CBC_SHA", "TLS 1.2"),
    "0x0035": ("TLS_RSA_WITH_AES_256_CBC_SHA", "TLS 1.2"),
    "0x003c": ("TLS_RSA_WITH_AES_128_CBC_SHA256", "TLS 1.2"),
    "0x003d": ("TLS_RSA_WITH_AES_256_CBC_SHA256", "TLS 1.2"),
    "0xc018": ("TLS_ECDH_anon_WITH_AES_128_CBC_SHA", "TLS 1.2"),
    "0xc019": ("TLS_ECDH_anon_WITH_AES_256_CBC_SHA", "TLS 1.2"),
    "0x0034": ("TLS_DH_anon_WITH_AES_128_CBC_SHA", "TLS 1.2"),
    "0x003a": ("TLS_DH_anon_WITH_AES_256_CBC_SHA", "TLS 1.2")
}

def analyze_and_export(pcap_file, output_base_name="tls_analysis"):
    txt_filename = f"{output_base_name}.txt"
    png_filename = f"{output_base_name}.png"
    
    # --- PHASE 1: DATA GATHERING ---
    if os.path.exists(txt_filename):
        print(f"Found existing cached data in '{txt_filename}'. Skipping PCAP processing...")
        # Load the data directly from the text file into a pandas DataFrame
        df = pd.read_csv(txt_filename, sep='\t')
    else:
        print(f"Analyzing '{pcap_file}'...")
        print("Extracting TLS packets. This may take a few moments depending on file size...\n")
        
        try:
            cap = pyshark.FileCapture(pcap_file, display_filter='tls.handshake.type == 2')
        except FileNotFoundError:
            print(f"Error: Could not find the file '{pcap_file}'. Please check the path.")
            return

        cipher_counts = Counter()

        # Process packets
        for pkt in cap:
            try:
                cipher_hex = pkt.tls.handshake_ciphersuite
                cipher_info = CIPHER_MAP.get(cipher_hex, (f"Unknown Cipher ({cipher_hex})", "Unknown"))
                cipher_counts[cipher_info] += 1
            except AttributeError:
                continue
                
        cap.close()

        if not cipher_counts:
            print("No successful TLS negotiations found in this PCAP.")
            return

        print("Data extracted successfully. Saving cache...")
        
        # Prepare data for the table
        table_data = []
        for (cipher_name, protocol), count in cipher_counts.most_common():
            table_data.append([count, protocol, cipher_name])

        # Create a pandas DataFrame
        df = pd.DataFrame(table_data, columns=["Count", "Protocol", "Cipher Suite Algorithm"])

        # SAVE TO TEXT FILE
        df.to_csv(txt_filename, sep='\t', index=False) 
        print(f"-> Cached data saved to text file: {txt_filename}")

    # --- PHASE 2: IMAGE GENERATION ---
    print("Generating image...")
    
    # Calculate figure height dynamically based on the number of rows
    fig, ax = plt.subplots(figsize=(12, len(df) * 0.4 + 1)) 
    ax.axis('tight')
    ax.axis('off')

    # Create the visual table with EXPLICIT column widths
    table = ax.table(cellText=df.values, 
                     colLabels=df.columns, 
                     colWidths=[0.10, 0.15, 0.75], 
                     loc='center', 
                     cellLoc='left')

    # Style the table
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 1.8) # Adjust overall scaling

    # Make headers bold and visually distinct
    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_text_props(weight='bold')
            cell.set_facecolor('#f0f0f0') # Light gray background for headers

    # Save to PNG
    plt.savefig(png_filename, bbox_inches='tight', dpi=300)
    print(f"-> Image saved to: {png_filename}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pcap_to_table.py <path_to_pcap> [output_base_name]")
    else:
        pcap_path = sys.argv[1]
        
        # User can specify a custom base name (without extension)
        if len(sys.argv) > 2:
            base_name = sys.argv[2]
            # Strip off extension if the user accidentally typed it
            base_name = os.path.splitext(base_name)[0]
            analyze_and_export(pcap_path, base_name)
        else:
            analyze_and_export(pcap_path)