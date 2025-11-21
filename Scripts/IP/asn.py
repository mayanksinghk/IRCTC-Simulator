import os
import json
import ipaddress
import argparse
import multiprocessing
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import geoip2.database
import requests

# -----------------------------
# CONFIG: Cloud / CDN / ISPs
# -----------------------------
CLOUD_PROVIDERS = {
    "AWS": [16509, 14618, 7224, 8075],
    "Azure": [8075, 12076, 13194],
    "GCP": [15169, 36040],
    "Cloudflare": [13335, 395747],
    "Akamai": [16625, 20940, 35919],
    "Fastly": [54113],
    "OVH": [16276, 16265, 16267],
    "Hetzner": [24940, 28871],
    "DigitalOcean": [14061, 14046],
    "Linode": [63949, 131249],
    "Alibaba Cloud": [37963, 45102],
    "Tencent Cloud": [37963],
    "Rackspace": [19984],
    "Airtel": [9498],
    "Jio": [55836],
    "RailTel": [24186],
    "CRIS": [45596],
    "Tata Communications": [4755]
}

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def log(msg):
    print(f"[+] {msg}")

def auto_worker_count():
    return max(1, multiprocessing.cpu_count() - 1)

def is_public_ip(ip):
    try:
        return ipaddress.ip_address(ip).is_global
    except ValueError:
        return False

def lookup_asn(ip, reader, online=False):
    """Return ASN number, org name."""
    try:
        r = reader.asn(ip)
        return r.autonomous_system_number, r.autonomous_system_organization
    except Exception:
        if online:
            try:
                resp = requests.get(f'https://rdap.arin.net/registry/ip/{ip}', timeout=5)
                data = resp.json()
                asn = int(data.get('asn', 0))
                org = data.get('name', 'Unknown')
                return asn, org
            except Exception:
                return None, None
        return None, None

def detect_provider(asn, org):
    for prov, asns in CLOUD_PROVIDERS.items():
        if asn in asns:
            return prov
    return org or "Unknown"

def chunk_list(lst, n):
    k, m = divmod(len(lst), n)
    return [lst[i*k + min(i, m):(i+1)*k + min(i+1, m)] for i in range(n)]

def process_chunk(chunk_ips, reader, online_asn):
    """Process chunk of IPs for ASN lookup."""
    asn_to_ips = defaultdict(set)
    asn_org_map = {}
    for ip in chunk_ips:
        asn, org = lookup_asn(ip, reader, online=online_asn)
        if asn is None:
            continue
        asn_to_ips[asn].add(ip)
        if asn not in asn_org_map:
            asn_org_map[asn] = org
    return asn_to_ips, asn_org_map

def merge_dicts(dicts):
    merged = defaultdict(set)
    for d in dicts:
        for k, v in d.items():
            merged[k].update(v)
    return merged

def save_output(file_basename, out_dir, asn_to_ips, asn_org_map):
    folder_path = os.path.join(out_dir, file_basename)
    os.makedirs(folder_path, exist_ok=True)
    stats = {
        "input_file": file_basename,
        "total_unique_ips": sum(len(v) for v in asn_to_ips.values()),
        "asn_count": len(asn_to_ips),
        "asn_details": {},
        "ip_provider": {}
    }

    for asn, ips in asn_to_ips.items():
        ips_sorted = sorted(ips)
        provider = detect_provider(asn, asn_org_map.get(asn, "Unknown"))
        
        # Save per-ASN file
        asn_file = os.path.join(folder_path, f"{file_basename}_AS{asn}.txt")
        with open(asn_file, 'w') as f:
            f.write(f"# ASN: AS{asn}\n")
            f.write(f"# Organization: {asn_org_map.get(asn, 'Unknown')}\n")
            f.write(f"# Provider/CDN: {provider}\n")
            f.write(f"# Total IPs: {len(ips_sorted)}\n\n")
            f.write("\n".join(ips_sorted))

        # Update stats
        stats['asn_details'][f"AS{asn}"] = {
            "org": asn_org_map.get(asn, "Unknown"),
            "provider": provider,
            "cidrs": [],  # optional CIDR list
            "total_ips": len(ips_sorted),
            "file": asn_file
        }

        for ip in ips_sorted:
            stats['ip_provider'][ip] = provider

    # Save overall stats.json
    stats_file = os.path.join(folder_path, f"{file_basename}_stats.json")
    with open(stats_file, 'w') as sf:
        json.dump(stats, sf, indent=2)

    return stats

# -----------------------------
# PROCESS SINGLE FILE
# -----------------------------
def process_single_file(args_tuple):
    file_path, out_dir, asn_db, whois_flag, online_asn = args_tuple
    file_basename = os.path.splitext(os.path.basename(file_path))[0]
    log(f"Processing file {file_basename}")

    # Read and filter IPs
    with open(file_path) as f:
        lines = [line.strip() for line in f if line.strip()]
    ips = []
    for line in lines:
        ip = line.split(":")[0].strip()  # IP:Port → take IP
        if is_public_ip(ip):
            ips.append(ip)
    if not ips:
        log(f"No public IPs in {file_basename}, skipping")
        return {"file": file_basename, "status": "skipped"}

    # GeoLite2 reader
    reader = geoip2.database.Reader(asn_db)

    # Chunk IPs for per-file threads
    num_threads = min(len(ips), auto_worker_count())
    chunks = chunk_list(ips, num_threads)

    asn_results = []
    org_results = []

    # Per-file multi-threaded processing
    with ThreadPoolExecutor(max_workers=len(chunks)) as exe:
        futures = [exe.submit(process_chunk, chunk, reader, online_asn) for chunk in chunks]
        for future in tqdm(as_completed(futures), total=len(futures), desc=f"{file_basename}"):
            asn_map, org_map = future.result()
            asn_results.append(asn_map)
            org_results.append(org_map)

    # Merge results
    asn_to_ips = merge_dicts(asn_results)
    asn_org_map = {}
    for org_map in org_results:
        asn_org_map.update(org_map)

    # Save output
    stats = save_output(file_basename, out_dir, asn_to_ips, asn_org_map)
    log(f"Finished file {file_basename}")
    return stats

# -----------------------------
# MAIN FUNCTION
# -----------------------------
def main():
    parser = argparse.ArgumentParser(description="Enhanced ASN grouping for public IPs with provider/CDN detection")
    parser.add_argument("--input-dir", "-i", required=True)
    parser.add_argument("--output-dir", "-o", required=True)
    parser.add_argument("--asn-db", default="GeoLite2-ASN.mmdb")
    parser.add_argument("--workers", "-w", type=int, default=None)
    parser.add_argument("--whois", action="store_true")
    parser.add_argument("--online-asn", action="store_true", help="Enable online ASN lookup if not in DB")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    files = [os.path.join(args.input_dir, f) for f in os.listdir(args.input_dir) if f.lower().endswith(".txt")]
    if not files:
        log("No .txt files found")
        return

    workers = args.workers or auto_worker_count()
    log(f"Using {workers} workers")
    log(f"Total files to process: {len(files)}")
    task_args = [(f, args.output_dir, args.asn_db, args.whois, args.online_asn) for f in files]

    # Process files in parallel
    with multiprocessing.Pool(processes=workers) as pool:
        results = pool.map(process_single_file, task_args)

    # Save summary
    summary_path = os.path.join(args.output_dir, "summary.json")
    with open(summary_path, "w") as sf:
        json.dump({"files_processed": len(files), "details": results}, sf, indent=2)
    log(f"Summary saved to {summary_path}")

if __name__ == "__main__":
    main()
