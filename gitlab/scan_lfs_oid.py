#!/usr/bin/env python3
"""Scan directories, compute sha256 OID for LFS-eligible files, output OID->path mapping.

Usage:
    python3 /tmp/scan_lfs_oid.py -f /tmp/all_dirs_full.txt -j 24
    python3 /tmp/scan_lfs_oid.py /path/to/model1 /path/to/model2 -j 24
"""

import argparse
import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

LFS_EXTENSIONS = {
    ".safetensors", ".bin", ".pt", ".pth", ".ckpt", ".h5",
    ".onnx", ".pb", ".tflite", ".mlmodel", ".model", ".ot", ".ftz", ".gguf",
    ".pkl", ".joblib", ".msgpack", ".npy", ".npz", ".arrow", ".parquet",
    ".7z", ".bz2", ".gz", ".rar", ".tar", ".tgz", ".xz", ".zip", ".zst",
    ".pickle", ".wasm",
}


def has_lfs_extension(filepath):
    name = filepath.lower()
    if ".tar." in name:
        return True
    _, ext = os.path.splitext(name)
    return ext in LFS_EXTENSIONS


def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(8 * 1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def compute_oid(filepath):
    """Returns (filepath, oid, size, error)."""
    try:
        size = os.path.getsize(filepath)
        oid = sha256_file(filepath)
        return filepath, oid, size, None
    except Exception as e:
        return filepath, None, 0, str(e)


def main():
    parser = argparse.ArgumentParser(description="Scan dirs and compute LFS OIDs via sha256")
    parser.add_argument("dirs", nargs="*", help="Directory paths to scan")
    parser.add_argument("-f", "--dirs-file", help="File with directory paths (one per line)")
    parser.add_argument("-j", "--jobs", type=int, default=24, help="Parallel workers (default: 24)")
    parser.add_argument("-o", "--output", default="/tmp/oid_mapping_lfs.json", help="Output JSON path")
    args = parser.parse_args()

    directories = list(args.dirs) if args.dirs else []
    if args.dirs_file:
        with open(args.dirs_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    directories.append(line)

    if not directories:
        print("No directories specified", file=sys.stderr)
        sys.exit(1)

    print(f"[{datetime.now():%H:%M:%S}] Scanning {len(directories)} directories for LFS-eligible files...")

    all_files = []
    for d in directories:
        if not os.path.isdir(d):
            print(f"  WARN: directory not found: {d}", file=sys.stderr)
            continue
        count = 0
        for root, _, files in os.walk(d):
            for fname in files:
                fpath = os.path.join(root, fname)
                if has_lfs_extension(fname) and os.path.isfile(fpath) and not os.path.islink(fpath):
                    all_files.append(fpath)
                    count += 1
        print(f"  {d}: {count} LFS files found")

    print(f"[{datetime.now():%H:%M:%S}] Total: {len(all_files)} files to compute OIDs (jobs={args.jobs})")

    oid_map = {}  # oid -> {size, files: [abs_path, ...]}
    errors = []
    done = 0

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(compute_oid, fp): fp for fp in all_files}
        for future in as_completed(futures):
            filepath, oid, size, err = future.result()
            done += 1
            if done % 50 == 0 or done == len(all_files):
                print(f"  [{datetime.now():%H:%M:%S}] {done}/{len(all_files)} computed")

            if err:
                errors.append({"file": filepath, "error": err})
                continue

            if oid not in oid_map:
                oid_map[oid] = {"size": size, "files": []}
            oid_map[oid]["files"].append(filepath)

    total_size = sum(info["size"] for info in oid_map.values() if info["size"])
    output = {
        "timestamp": datetime.now().isoformat(),
        "total_files": len(all_files),
        "total_oids": len(oid_map),
        "total_size_gb": round(total_size / (1024**3), 2),
        "errors": errors,
        "oids": oid_map,
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n[{datetime.now():%H:%M:%S}] Done!")
    print(f"  Files scanned: {len(all_files)}")
    print(f"  Unique OIDs:   {len(oid_map)}")
    print(f"  Total size:    {round(total_size / (1024**3), 1)} GB")
    print(f"  Errors:        {len(errors)}")
    print(f"  Output:        {args.output}")


if __name__ == "__main__":
    main()
