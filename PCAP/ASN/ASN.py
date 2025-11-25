#!/usr/bin/env python3
import os
import re
import ipaddress
import maxminddb
import pandas as pd
import pytricia
from collections import defaultdict
import argparse
from pathlib import Path

# ============================================================
# IPv4 Extractor
# ============================================================
ipv4_regex = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')

def extract_ipv4(line):
    m = ipv4_regex.search(line)
    return m.group(0) if m else None


# ============================================================
# Private IP Check
# ============================================================
def is_private_ip(ip):
    try:
        return ipaddress.ip_address(ip).is_private
    except:
        return True


# ============================================================
# Load All Public IPv4s
# ============================================================
def load_public_ips(filepath):
    ips = set()
    with open(filepath, "r") as f:
        for raw in f:
            ip = extract_ipv4(raw)
            if ip and not is_private_ip(ip):
                ips.add(ip)
    return sorted(ips)


# ============================================================
# Build ASN → Prefix Data Using MMDB
# ============================================================
def build_asn_data(ips, mmdb_path):
    reader = maxminddb.open_database(mmdb_path)

    asn_to_name = {}
    asn_to_prefixes = defaultdict(set)

    for ip in ips:
        try:
            rec, prefix_len = reader.get_with_prefix_len(ip)
        except:
            continue

        if not rec:
            continue

        asn = rec.get("autonomous_system_number")
        asn_name = rec.get("autonomous_system_organization")

        if not asn:
            continue

        asn = str(asn).strip()

        if asn_name:
            asn_to_name[asn] = asn_name

        if prefix_len is not None:
            try:
                network = ipaddress.ip_network(f"{ip}/{prefix_len}", strict=False)
                asn_to_prefixes[asn].add(str(network))
            except:
                pass

    reader.close()
    return asn_to_name, asn_to_prefixes


# ============================================================
# Save Excel in HackerTarget Format
# ============================================================
def save_excel(output_path, asn_to_name, asn_to_prefixes):

    rows = []
    for asn in sorted(asn_to_prefixes.keys(), key=lambda x: int(x)):
        as_name = asn_to_name.get(asn, "")
        prefixes = "\n".join(sorted(asn_to_prefixes[asn]))
        rows.append([asn, as_name, prefixes])

    df = pd.DataFrame(rows, columns=["AS #", "AS Name", "AS Prefixes"])
    df.to_excel(output_path, index=False, startrow=1)

    print(f"[✓] Saved HackerTarget-style Excel: {output_path}")


# ============================================================
# Summary of Excel
# ============================================================
def summarize_excel(path):
    print("\n========== SUMMARY ==========")

    df = pd.read_excel(path, header=None)

    expected_cols = ["AS #", "AS Name", "AS Prefixes"]
    header_index = None

    for i in range(10):
        row_vals = df.iloc[i].fillna("").astype(str).str.strip().tolist()
        if row_vals == expected_cols:
            header_index = i
            break

    if header_index is None:
        raise ValueError("Header row not found")

    df.columns = expected_cols
    df = df.iloc[header_index+1:].reset_index(drop=True)

    df["Prefix Count"] = df["AS Prefixes"].fillna("").apply(lambda x: len(str(x).split("\n")))

    print("Total ASNs:", df.shape[0])
    print("Total Prefixes:", df["Prefix Count"].sum())

    print("\nTop 10 AS by Prefix Count:")
    print(df.sort_values("Prefix Count", ascending=False).head(10)[["AS #", "AS Name", "Prefix Count"]])



# ============================================================
# Load HackerTarget Excel → Prefixes
# ============================================================
def load_hackertarget_asn_file(file_path):
    df = pd.read_excel(file_path, header=None)

    df.columns = df.iloc[1]      # header row
    df = df.iloc[2:].reset_index(drop=True)

    prefixes = []

    for idx in df.index:
        asn = str(df.at[idx, "AS #"]).strip()
        asn_name = str(df.at[idx, "AS Name"]).strip()
        block = str(df.at[idx, "AS Prefixes"]).strip()

        for cidr in block.split("\n"):
            cidr = cidr.strip()
            if not cidr:
                continue

            try:
                net = ipaddress.ip_network(cidr, strict=False)
                if isinstance(net, ipaddress.IPv4Network):
                    prefixes.append((str(net), asn, asn_name))
            except:
                pass

    return prefixes


# ============================================================
# Build PyTricia Prefix Tree
# ============================================================
def load_prefixes_from_folder(folder_path):
    pt = pytricia.PyTricia(32)

    for file in os.listdir(folder_path):
        if not file.endswith(".xlsx"):
            continue

        full = os.path.join(folder_path, file)
        print(f"[+] Loading: {file}")

        prefix_tuples = load_hackertarget_asn_file(full)

        for net, asn, asn_name in prefix_tuples:
            pt[net] = (asn, asn_name)

    print("[✓] PyTricia tree built.")
    return pt


def match_ip_to_asn(ip, pt):
    try:
        return pt.get(ip, (None, None))
    except:
        return (None, None)


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="ASN Lookup Pipeline")
    parser.add_argument("-i", "--input", type=str, default="/home/mayank/Desktop/IRCTC/IRCTC-Simulator/Data/Unique_IP_all/12_all.txt", help="Path to the file containing IP addresses")
    parser.add_argument("-m", "--mmdb-path", type=str, default="/home/mayank/Desktop/IRCTC/IRCTC-Simulator/Data/GeoLite2-City/GeoLite2-ASN.mmdb", help="Path to the Max Mind DB file")
    parser.add_argument("-o", "--output_dir", type=str, default="ASN-IP", help="Folder containing ASN Excel files") 

    args = parser.parse_args()
    IP_file = args.input
    mmdb_path = args.mmdb_path
    input_folder = args.output_dir
    master_excel = "asn_lookup.xlsx"
    # ----------------------------

    print("[+] Loading IPv4s...")
    ips = load_public_ips(IP_file)
    print(f"    → {len(ips)} public IPs")

    print("[+] Building ASN DB...")
    asn_to_name, asn_to_prefixes = build_asn_data(ips, mmdb_path)

    master_excel = input_folder + "/" + master_excel
    print("[+] Saving master Excel...")
    save_excel(master_excel, asn_to_name, asn_to_prefixes)

    print("[+] Summary:")
    summarize_excel(master_excel)


    print("\n[+] Building PyTricia prefix tree from asn lookup table...")
    pt = load_prefixes_from_folder(input_folder)

    print("[+] Matching IPs to ASN...")
    matched = []
    unmatched = []

    for ip in ips:
        asn, asn_name = match_ip_to_asn(ip, pt)
        if asn:
            matched.append([ip, asn, asn_name])
        else:
            unmatched.append(ip)

    # Save matched
    ip_asn_csv = input_folder + "/" + Path(IP_file).stem +  "_matched_ips.csv"
    matched_df = pd.DataFrame(matched, columns=["IP", "ASN", "ASN Name"])
    matched_df.to_csv(ip_asn_csv, index=False)
    print(f"[✓] Saved IP → ASN mapping CSV: {ip_asn_csv}")


    with open("unmatched_ips.txt", "w") as f:
        f.write("\n".join(unmatched))

    print("\n[✓] Pipeline complete.")
    print("   → matched_ips.csv")
    print("   → unmatched_ips.txt")
    print("   → asn_master.xlsx")

    # ----------------------------
    # Summary Statistics
    # ----------------------------
    total = len(ips)
    matched_count = len(matched)
    unmatched_count = len(unmatched)

    matched_pct = (matched_count / total * 100) if total else 0
    unmatched_pct = (unmatched_count / total * 100) if total else 0

    print("\n========== SUMMARY ==========")
    print(f"Total IPs processed  : {total}")
    print(f"Matched IPs          : {matched_count} ({matched_pct:.2f}%)")
    print(f"Unmatched IPs        : {unmatched_count} ({unmatched_pct:.2f}%)")
    print("================================\n")

    # ----------------------------
    # ASN Distribution Statistics
    # ----------------------------
    print("\n========== ASN DISTRIBUTION ==========")

    if matched_count == 0:
        print("No matched IPs to analyze.")
    else:
        # Count IPs per ASN Name
        asn_stats = matched_df["ASN Name"].value_counts()

        for asn_name, count in asn_stats.items():
            pct = (count / total) * 100
            print(f"{asn_name:<40} : {count:5d}  ({pct:.2f}%)")

    print("======================================\n")



if __name__ == "__main__":
    main()
