"""Freeze an availability-selected LitQA2 pilot; never selects on model outputs.

Run once with --discover to create the manifest/splits. Existing splits cannot be
overwritten. Subsequent corpus restoration uses pqa-reflect prepare-corpus.
Requires the optional `data` dependency group (pyarrow).
"""

import argparse
import hashlib
import json
import random
import re
import string
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
import pyarrow.parquet as pq

from paperqa_reflect.config import write_json
from paperqa_reflect.corpus import jats_text
from paperqa_reflect.data import sha256

REVISION = "5c77cec648430f30611808808861eb86f81d5eaa"
PARQUET_SHA256 = "3e578fdaaa4728a77e884954dbf85ae0e3899791631a3be0838313b3e2334114"
DATA_URL = f"https://huggingface.co/datasets/futurehouse/lab-bench/resolve/{REVISION}/LitQA2/train-00000-of-00001.parquet"
ORDER_PREFIX = "ikt464-pilot-v1:"
PER_SPLIT = 8


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )


def normalize(value):
    return re.sub(r"[^a-z0-9]", "", value.lower())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discover", action="store_true", required=True)
    args = parser.parse_args()
    assert args.discover
    root = Path.cwd()
    manifest = root / "data/manifests/litqa-pilot.json"
    if manifest.exists():
        raise SystemExit("Frozen pilot already exists; refusing to change its questions or corpus.")
    cache = root / ".cache/datasets/lab-bench"
    cache.mkdir(parents=True, exist_ok=True)
    corpus = root / "data/corpus/litqa-pilot"
    corpus.mkdir(parents=True, exist_ok=True)
    parquet = cache / "litqa2.parquet"
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        if not parquet.exists():
            response = client.get(DATA_URL)
            response.raise_for_status()
            parquet.write_bytes(response.content)
        if sha256(parquet) != PARQUET_SHA256:
            raise ValueError("Unexpected dataset snapshot; refusing to select questions")
        rows = pq.read_table(parquet).to_pylist()
        rows.sort(key=lambda row: digest((ORDER_PREFIX + row["id"]).encode()))
        questions = {"dev": [], "holdout": []}
        keys = {"dev": [], "holdout": []}
        selected, log, documents, seen_sources = [], [], [], set()
        for rank, row in enumerate(rows, 1):
            if len(selected) == 2 * PER_SPLIT:
                break
            aliases = {url.split("doi.org/")[-1].lower() for url in row["sources"]}
            entry = {"rank": rank, "id": row["id"], "source_dois": sorted(aliases)}
            if aliases & seen_sources:
                log.append(entry | {"excluded": "source overlaps an already selected question"})
                continue
            discovery = cache / "discovery" / (row["id"] + ".json")
            if discovery.exists():
                results = json.loads(discovery.read_text(encoding="utf-8"))["results"]
            else:
                results = []
                for doi in sorted(aliases):
                    response = client.get(
                        "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                        params={"query": "DOI:" + doi, "format": "json", "resultType": "core"},
                    )
                    response.raise_for_status()
                    results.extend(response.json()["resultList"]["result"])
                    time.sleep(0.2)
                write_json(discovery, {"id": row["id"], "results": results})
            candidates = sorted(
                [r for r in results if r.get("pmcid") and r.get("isOpenAccess") == "Y"],
                key=lambda r: r["pmcid"],
            )
            doc = None
            errors = []
            for meta in candidates:
                pmcid = meta["pmcid"]
                url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
                xml_path = cache / (pmcid + ".xml")
                try:
                    if not xml_path.exists():
                        response = client.get(url)
                        response.raise_for_status()
                        xml_path.write_bytes(response.content)
                    payload = xml_path.read_bytes()
                    text = jats_text(payload)
                    article = ET.fromstring(payload)
                    filename = pmcid + ".txt"
                    (corpus / filename).write_bytes(text)
                    authors = [
                        a["fullName"]
                        for a in meta.get("authorList", {}).get("author", [])
                        if a.get("fullName")
                    ]
                    doc = {
                        "file": filename,
                        "sha256": digest(text),
                        "url": url,
                        "source_sha256": digest(payload),
                        "transform": "jats-body-text-v1",
                        "pmcid": pmcid,
                        "doi": meta["doi"],
                        "title": meta["title"],
                        "year": int(meta["pubYear"]),
                        "authors": authors,
                        "journal": meta.get("journalInfo", {}).get("journal", {}).get("title", ""),
                        "citation": f"{meta['authorString']} {meta['title']} ({meta['pubYear']}). doi:{meta['doi']}",
                        "license_text": " ".join(
                            "".join(n.itertext()) for n in article.findall(".//permissions/license")
                        ),
                        "text_characters": len(text.decode("utf-8")),
                    }
                    break
                except (httpx.HTTPError, ValueError, ET.ParseError) as error:
                    errors.append(f"{pmcid}: {type(error).__name__}: {error}")
            if doc is None:
                log.append(
                    entry | {"excluded": "no accessible Europe PMC OA JATS body", "errors": errors}
                )
                continue
            split = "dev" if len(selected) % 2 == 0 else "holdout"
            choices = [row["ideal"], *row["distractors"]]
            if len(set(choices)) != len(choices) or not 2 <= len(choices) <= 26:
                # Keep this eligibility rule explicit; never repair published answers silently.
                (corpus / doc["file"]).unlink()
                log.append(entry | {"excluded": "duplicate options or unsupported option count"})
                continue
            random.Random(ORDER_PREFIX + row["id"]).shuffle(choices)
            options = dict(zip(string.ascii_uppercase, choices))
            questions[split].append(
                {"id": row["id"], "question": row["question"], "options": options}
            )
            keys[split].append(
                {
                    "id": row["id"],
                    "answer": next(k for k, v in options.items() if v == row["ideal"]),
                    "ideal": row["ideal"],
                    "support": row["key-passage"],
                    "source_dois": sorted(aliases),
                    "source_files": [doc["file"]],
                    "key_passage_exact_normalized_match": (
                        normalize(row["key-passage"]) in normalize(text.decode("utf-8"))
                        if row["key-passage"]
                        else None
                    ),
                    "canary": row["canary"],
                }
            )
            selected.append(row["id"])
            seen_sources.update(aliases)
            documents.append(doc)
            log.append(entry | {"selected": split, "file": doc["file"]})
            print(split, len(questions[split]), row["id"], doc["file"], flush=True)
        if len(selected) != 2 * PER_SPLIT:
            raise RuntimeError("Not enough eligible articles; no final manifest written")
    write_json(manifest, {"name": "litqa-pilot-v1", "documents": documents})
    for split, question_rows in questions.items():
        write_jsonl(root / f"data/questions/litqa-{split}.jsonl", question_rows)
        write_jsonl(root / f"data/gold/litqa-{split}.jsonl", keys[split])
    write_json(
        root / "data/manifests/litqa-selection.json",
        {
            "dataset": "futurehouse/lab-bench",
            "configuration": "LitQA2",
            "upstream_split": "train",
            "revision": REVISION,
            "url": DATA_URL,
            "sha256": sha256(parquet),
            "rows": len(rows),
            "license": "CC-BY-SA-4.0",
            "selection": "SHA256(prefix + id) ascending; first 16 eligible unique sources, alternate dev/holdout",
            "prefix": ORDER_PREFIX,
            "eligibility": "Europe PMC OA JATS main body >=5000 characters; unique options, 2..26 choices; no source overlap",
            "not_used_for_selection": ["model outputs", "answer correctness", "key passage match"],
            "selected_ids": selected,
            "attempted": log,
        },
    )
    print("Frozen: 8 development + 8 reserved questions, 16 article texts.")


if __name__ == "__main__":
    main()
