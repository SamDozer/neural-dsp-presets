"""Download all attachments (presets) from a Discourse thread - parallel & resumable.
Usage: python download_presets.py <topic_id> [output_folder]
Re-running skips what is already downloaded (tracked in .manifest.json).
Anything that can't be downloaded is listed in NOT_DOWNLOADED.txt in the output folder.
"""
import json, os, re, sys, time, threading, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from html import unescape

BASE = "https://unity.neuraldsp.com"
TOPIC = int(sys.argv[1])
OUT = sys.argv[2] if len(sys.argv) > 2 else f"presets_{TOPIC}"
HDR = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
SKIP_HOSTS = ("youtube.com", "youtu.be", "neuraldsp.com/t/", "neuraldsp.com/u/", "neuraldsp.com/c/", "neuraldsp.com/tag")
MEDIA = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mp3", ".wav", ".m4a")
EXTERNAL = re.compile(r"dropbox|mediafire|mega\.nz|onedrive|1drv|wetransfer|\.(xml|zip|rar|7z)(\?|$)", re.I)
BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
lock = threading.Lock()


def get(url, binary=False):
    for attempt in range(6):
        try:
            h = HDR if not binary else {**HDR, "Accept": "*/*"}  # Dropbox serves a web page if Accept is json
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=45) as r:
                data = r.read()
            return data if binary else json.loads(data)
        except Exception:
            if attempt == 5:
                raise
            time.sleep(2 * (attempt + 1))


def unique(name):
    base, ext = os.path.splitext(name)
    dest, k = os.path.join(OUT, name), 2
    while os.path.exists(dest):
        dest = os.path.join(OUT, f"{base} ({k}){ext}")
        k += 1
    return dest


def parse(posts):
    """-> list of (post_number, original_href, download_url, filename_or_None)"""
    jobs, seen = [], set()
    for p in posts:
        for href, text in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', p["cooked"], re.S):
            href = unescape(href)
            text = unescape(re.sub(r"<[^>]+>", "", text)).strip()
            path = href.lower().split("?")[0]
            d = re.search(r"drive\.google\.com/(?:file/d/|open\?id=)([\w-]+)", href)
            name = None
            fo = re.search(r"drive\.google\.com/drive/folders/([\w-]+)", href)
            if fo:  # public Drive folder: list its files, then treat each as a file link
                try:
                    html = get(f"https://drive.google.com/embeddedfolderview?id={fo.group(1)}", binary=True).decode("utf8", "ignore")
                    for fid, title in re.findall(r'/file/d/([\w-]+)/view[^>]*>.*?flip-entry-title">([^<]*)<', html, re.S):
                        u = f"https://drive.usercontent.google.com/download?id={fid}&export=download&confirm=t"
                        if u not in seen:
                            seen.add(u); jobs.append((p["post_number"], href, u, BAD.sub("_", unescape(title))))
                except Exception as e:
                    print("folder fail", href, e)
                continue
            if d:
                url = f"https://drive.usercontent.google.com/download?id={d.group(1)}&export=download&confirm=t"
            elif "/uploads/" in href:
                if path.endswith(MEDIA):
                    continue
                url = urllib.parse.urljoin(BASE, href)
                name = text if "." in text else urllib.parse.unquote(os.path.basename(path))
            elif href.startswith("http") and not path.endswith(MEDIA) and not any(s in href for s in SKIP_HOSTS) and EXTERNAL.search(href):
                url = href
                if "dropbox.com" in url:
                    url = re.sub(r"([?&])dl=0", r"\1dl=1", url) + ("" if "dl=1" in url else ("&" if "?" in url else "?") + "dl=1")
            else:
                continue
            if url not in seen:
                seen.add(url)
                jobs.append((p["post_number"], href, url, BAD.sub("_", name) if name else None))
    return jobs


manifest_path = os.path.join(OUT, ".manifest.json")
os.makedirs(OUT, exist_ok=True)
manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else {}

topic = get(f"{BASE}/t/{TOPIC}.json")
ids = topic["post_stream"]["stream"]
print(f"{topic['title']}: {len(ids)} posts", flush=True)

chunks = [ids[i:i + 20] for i in range(0, len(ids), 20)]
with ThreadPoolExecutor(4) as ex:
    pages = ex.map(lambda c: get(f"{BASE}/t/{TOPIC}/posts.json?" + "&".join(f"post_ids[]={i}" for i in c))["post_stream"]["posts"], chunks)
    posts = [p for page in pages for p in page]

jobs = parse(posts)
print(f"{len(jobs)} files found", flush=True)
failed, counts = [], {"new": 0, "skipped": 0}


def work(job):
    num, href, url, name = job
    if url in manifest and os.path.exists(os.path.join(OUT, manifest[url])):
        counts["skipped"] += 1
        return
    try:
        data = get(url, binary=True)
        if data[:15].lower().startswith((b"<!doctype", b"<html")):
            raise ValueError("got a web page, not a file")
        if name is None:  # Drive / external: take the preset name from the file itself
            m = re.search(rb"presetName\w*\s*([^\x00-\x1f]{1,80}?)\s*presetPath", data)
            name = (BAD.sub("_", m.group(1).decode("utf8", "ignore").strip()) + ".xml") if m else \
                   BAD.sub("_", urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(url).path))) or "preset.xml"
        with lock:
            dest = unique(name)
            open(dest, "wb").write(data)
            manifest[url] = os.path.basename(dest)
            counts["new"] += 1
        print("ok", os.path.basename(dest), flush=True)
    except Exception as e:
        with lock:
            failed.append((num, href))
        print("FAIL", href, e, flush=True)


# external hosts we can't fetch automatically (mega, mediafire, wetransfer...) go straight to the list
auto, manual = [], []
for j in jobs:
    (manual if re.search(r"mega\.nz|mediafire|wetransfer|1drv|onedrive", j[2]) else auto).append(j)
failed += [(n, h) for n, h, _, _ in manual]

with ThreadPoolExecutor(6) as ex:
    list(ex.map(work, auto))

json.dump(manifest, open(manifest_path, "w"), indent=1)
txt = os.path.join(OUT, "NOT_DOWNLOADED.txt")
if failed:
    open(txt, "w", encoding="utf8").write("".join(f"post {n}: {h}\n" for n, h in sorted(failed)))
elif os.path.exists(txt):
    os.remove(txt)
print(f"Done: {counts['new']} new, {counts['skipped']} already had, {len(failed)} not downloaded -> {os.path.abspath(OUT)}", flush=True)
