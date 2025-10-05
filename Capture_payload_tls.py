#!/usr/bin/env python3
"""
Estimate application-layer payload sizes from a TLS-encrypted pcap by stream.

Outputs:
 - Per-tcp.stream: total_encrypted_bytes, estimated_plaintext_bytes, records_count, cipher_suite
 - CSV file: tls_app_payload_estimates.csv
"""
import pyshark
import argparse
import csv
from collections import defaultdict

# Map common cipher suite names (or tokens) to properties we need:
# We identify AEAD by presence of 'GCM', 'CCM', 'POLY', 'CHACHA' etc.
# AEAD tag lengths: typically 16 bytes for GCM/Poly1305; CCM may be 8/16 (we assume 16)
AEAD_IDENTIFIERS = ['GCM', 'CCM', 'POLY1305', 'CHACHA', 'AES_256_GCM', 'AES_128_GCM']
# Map common HMAC lengths by algorithm substring
HMAC_MAP = {
    'SHA1': 20,
    'SHA224': 28,
    'SHA256': 32,
    'SHA384': 48,
    'SHA512': 64,
}

# Fallback assumptions
DEFAULT_AEAD_TAG = 16
DEFAULT_HMAC = 32

def detect_cipher_props(cipher_name):
    """
    Given a cipher string (as seen in field tls.handshake.ciphersuite or tls.record.version/ciphers),
    return dict: {'is_aead':bool,'tag_len':int,'mac_len':int}
    """
    if not cipher_name:
        return {'is_aead': None, 'tag_len': None, 'mac_len': None}

    u = cipher_name.upper()
    # AEAD detection
    for ident in AEAD_IDENTIFIERS:
        if ident in u:
            return {'is_aead': True, 'tag_len': DEFAULT_AEAD_TAG, 'mac_len': 0}
    # HMAC detection: try to find SHA*
    for hmac_name, size in HMAC_MAP.items():
        if hmac_name in u:
            return {'is_aead': False, 'tag_len': 0, 'mac_len': size}
    # fallback: if string contains 'AEAD' or 'GCM' anywhere
    if 'AEAD' in u or 'GCM' in u:
        return {'is_aead': True, 'tag_len': DEFAULT_AEAD_TAG, 'mac_len': 0}
    # unknown: return conservative guesses
    return {'is_aead': None, 'tag_len': None, 'mac_len': None}

def estimate_plain_from_record_len(record_len, props, tls_version=None):
    """
    Given TLS record length (the 2-byte length from TLS header), return estimated plaintext bytes for that record.
    Heuristics:
     - If AEAD: plaintext_est = record_len - tag_len
     - If HMAC: plaintext_est = record_len - mac_len  (ignores padding)
     - If unknown: return record_len (conservative).
    """
    if props is None:
        return record_len
    if props.get('is_aead') is True and props.get('tag_len') is not None:
        est = record_len - props['tag_len']
        # TLS 1.3 inner content-type and possible 1 byte padding - we cannot know padding, but inner content-type occupies 1 byte
        # Keep it simple: do not subtract content-type specially, users should be aware of 1 byte overhead for TLS1.3 inner type.
        return max(est, 0)
    elif props.get('is_aead') is False and props.get('mac_len') is not None:
        est = record_len - props['mac_len']
        return max(est, 0)
    else:
        # unknown: return record_len as conservative upper bound
        return record_len

def main():
    parser = argparse.ArgumentParser(description='Estimate application payload (pre-TLS) from pcap')
    parser.add_argument('--pcap', help='Path to capture.pcap')
    parser.add_argument('--filter', default='tls', help='Display filter for pyshark (default: tls)')
    args = parser.parse_args()

    cap = pyshark.FileCapture(args.pcap, display_filter=args.filter, keep_packets=False)

    # per-stream accumulators
    streams = defaultdict(lambda: {
        'encrypted_total': 0,
        'estimated_plain_total': 0,
        'record_count': 0,
        'cipher_candidates': set(),
        'tls_versions': set()
    })

    print("Scanning pcap (this can take a while for large files)...")
    for pkt in cap:
        # only process packets that have tcp.stream (some TLS-over-UDP etc. excluded)
        try:
            stream_id = int(pkt.tcp.stream)
        except Exception:
            continue

        # capture tls record length fields if present
        # pyshark exposes multiple tls.record_length fields for each record in a packet
        rec_lengths = []
        try:
            if hasattr(pkt, 'tls') and hasattr(pkt.tls, 'record_length'):
                # pkt.tls.record_length may be a RepeatedField — iterate
                # pyshark field object exposes 'all_fields' sometimes
                field = pkt.tls.record_length
                # try list-like first:
                if hasattr(field, 'all_fields'):
                    for f in field.all_fields:
                        try:
                            rec_lengths.append(int(f.show))
                        except:
                            pass
                else:
                    # single value
                    try:
                        rec_lengths.append(int(field.show))
                    except:
                        pass
        except Exception:
            pass

        # If no record lengths but packet has tls.handshake.ciphersuite or tls.handshake.version, capture those
        try:
            if hasattr(pkt.tls, 'handshake_ciphersuite'):
                # pyshark sometimes uses tls.handshake.ciphersuite
                try:
                    cs = pkt.tls.handshake_ciphersuite
                    streams[stream_id]['cipher_candidates'].add(str(cs))
                except:
                    pass
            if hasattr(pkt.tls, 'handshake_ciphersuite_value'):
                streams[stream_id]['cipher_candidates'].add(str(pkt.tls.handshake_ciphersuite_value))
        except Exception:
            pass

        try:
            # tls.handshake.version or tls.record.version
            if hasattr(pkt.tls, 'handshake_version'):
                streams[stream_id]['tls_versions'].add(str(pkt.tls.handshake_version))
            elif hasattr(pkt.tls, 'record_version'):
                streams[stream_id]['tls_versions'].add(str(pkt.tls.record_version))
        except Exception:
            pass

        # If we have record lengths, estimate plaintext contribution
        if rec_lengths:
            # choose a cipher candidate if known: prefer any candidate we observed
            cipher_str = None
            if streams[stream_id]['cipher_candidates']:
                cipher_str = next(iter(streams[stream_id]['cipher_candidates']))
            props = detect_cipher_props(cipher_str)
            for rl in rec_lengths:
                streams[stream_id]['encrypted_total'] += rl
                est = estimate_plain_from_record_len(rl, props)
                streams[stream_id]['estimated_plain_total'] += est
                streams[stream_id]['record_count'] += 1

    cap.close()

    # Output results
    filename_out = 'tls_app_payload_estimates.csv'
    with open(filename_out, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['tcp.stream', 'records', 'encrypted_total_bytes', 'estimated_plaintext_bytes', 'cipher_candidate', 'tls_versions'])
        grand_enc = 0
        grand_plain = 0
        for sid in sorted(streams.keys()):
            row = streams[sid]
            cipher_cand = ';'.join(row['cipher_candidates']) if row['cipher_candidates'] else ''
            tls_vs = ';'.join(row['tls_versions']) if row['tls_versions'] else ''
            writer.writerow([sid, row['record_count'], row['encrypted_total'], row['estimated_plain_total'], cipher_cand, tls_vs])
            grand_enc += row['encrypted_total']
            grand_plain += row['estimated_plain_total']

    print("Done. Results written to", filename_out)
    print(f"Grand totals — encrypted bytes: {grand_enc} bytes, estimated plaintext: {grand_plain} bytes")
    print("Per-stream breakdown saved to", filename_out)
    print("Notes:")
    print("- AEAD ciphers: script subtracts an assumed tag length (16 bytes).")
    print("- HMAC-based ciphers: script subtracts MAC length based on cipher name; padding is ignored (estimate may be slightly high).")
    print("- If the capture lacks the handshake, cipher detection may fail and the script will return conservative encrypted-byte == estimated-byte.")

if __name__ == '__main__':
    main()
