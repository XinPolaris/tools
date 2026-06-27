#!/usr/bin/env python3
import json
import shutil
from pathlib import Path
from urllib import parse, request


BASE_URL = "https://api-test.fotile.com"
API_PATH = "/v10/screen/recipes/list"
X_USER = "777777785"
ACCESS_TOKEN = "fotile_test_2021"
TIMEOUT = 15
ROOT_DIR = Path(r"D:\project_linux\04-ranghood-2\project_app\linux_app_fotile\project\04_hood\res\recipe\recipe_data")
OSS_IMAGE_180_PROCESS = "image/resize,m_fixed,h_180,w_180,limit_0/quality,q_50/rotate,0/rounded-corners,r_4/format,png"
OSS_IMAGE_480_PROCESS = "image/resize,m_fixed,h_480,w_480,limit_0/quality,q_50/rotate,0/rounded-corners,r_4/format,png"

RECIPE_IDS = [
    "69f07d0b1e90bb6efd6436b8"
]


def download_recipe_detail(recipe_id):
    url = BASE_URL.rstrip("/") + API_PATH
    body = json.dumps({"recipeId": recipe_id}).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-User": X_USER,
            "Access-Token": ACCESS_TOKEN,
        },
        method="POST",
    )
    with request.urlopen(req, timeout=TIMEOUT) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return json.loads(resp.read().decode(charset))


def get_detail_item(data):
    items = data.get("data", {}).get("list", [])
    if not items:
        return None
    return items[0]


def build_recipe_list_item(item):
    return {
        "_id": item.get("_id", ""),
        "name": item.get("name", ""),
        "images": item.get("images", []),
        "is_adapt": item.get("is_adapt", 0),
        "is_combain": item.get("is_combain", False),
    }


def build_recipe_list_data(items):
    return {
        "data": {
            "count": len(items),
            "list": items,
        },
        "code": 200,
        "msg": "success",
        "success": True,
    }


def suffix_from_url(url, default_suffix):
    path = parse.urlparse(url).path
    suffix = Path(path).suffix
    return suffix or default_suffix


def normalize_url(url):
    if not url:
        return ""
    parsed = parse.urlparse(url)
    if parsed.scheme:
        return url
    return BASE_URL.rstrip("/") + "/" + url.lstrip("/")


def add_oss_process(url, process):
    url = normalize_url(url)
    if not url or not process:
        return url

    separator = "&" if parse.urlparse(url).query else "?"
    return f"{url}{separator}x-oss-process={process}"


def download_file(url, out_file):
    url = normalize_url(url)
    if not url:
        return False

    req = request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "X-User": X_USER,
            "Access-Token": ACCESS_TOKEN,
        },
    )
    with request.urlopen(req, timeout=TIMEOUT) as resp:
        out_file.write_bytes(resp.read())
    print(f"saved {out_file}")
    return True


def download_recipe_assets(recipe_id, item, root_dir):
    net_pic_dir = root_dir / "pic"
    nav_video_dir = root_dir / "video"
    nav_cover_dir = net_pic_dir / "navCover"
    nav_prompts_dir = net_pic_dir / "navPrompts"

    for directory in (net_pic_dir, nav_video_dir, nav_cover_dir, nav_prompts_dir):
        directory.mkdir(parents=True, exist_ok=True)

    video_url = item.get("video", "")
    if video_url:
        video_suffix = suffix_from_url(video_url, ".mp4")
        download_file(video_url, nav_video_dir / f"{recipe_id}{video_suffix}")

    images = item.get("images", [])
    if images:
        cover_url = images[0]
        download_file(add_oss_process(cover_url, OSS_IMAGE_180_PROCESS), net_pic_dir / f"{recipe_id}.png")
        download_file(add_oss_process(cover_url, OSS_IMAGE_480_PROCESS), nav_cover_dir / f"{recipe_id}.png")

    devices = item.get("devices", [])
    if not devices:
        return

    prompts = devices[0].get("cooking_prompts_info", [])
    for prompt_index, prompts_item in enumerate(prompts):
        prompt_images = prompts_item.get("prompt_images", [])
        if not prompt_images:
            continue

        prompt_url = prompt_images[0]
        if not prompt_url:
            continue

        prompt_name = f"{recipe_id}_{prompt_index}.png"
        download_file(add_oss_process(prompt_url, OSS_IMAGE_480_PROCESS), nav_prompts_dir / prompt_name)


def main():
    root_dir = ROOT_DIR
    recipe_dir = root_dir
    if recipe_dir.exists():
        shutil.rmtree(recipe_dir)

    out_dir = root_dir / "json" 
    out_dir.mkdir(parents=True, exist_ok=True)

    recipe_list_items = []
    for recipe_id in RECIPE_IDS:
        data = download_recipe_detail(recipe_id)
        out_file = out_dir / f"{recipe_id}.json"
        out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"saved {out_file}")

        item = get_detail_item(data)
        if item:
            recipe_list_items.append(build_recipe_list_item(item))
            download_recipe_assets(recipe_id, item, root_dir)
        else:
            print(f"skip assets, empty detail list: {recipe_id}")

    recipe_list_file = out_dir / "recipe_list.json"
    recipe_list_file.write_text(
        json.dumps(build_recipe_list_data(recipe_list_items), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"saved {recipe_list_file}")


if __name__ == "__main__":
    main()
