import requests
import json
import os
import time
from datetime import datetime, timedelta

BASE_URL = "https://bsky.social/xrpc"
BSKY_HANDLE = os.getenv("BSKY_HANDLE")
BSKY_APP_PASSWORD = os.getenv("BSKY_APP_PASSWORD")

CACHE_FILE = "processed_mentions.json"

def login():
    print("🔐 Logging in...")
    res = requests.post(f"{BASE_URL}/com.atproto.server.createSession", json={
        "identifier": BSKY_HANDLE,
        "password": BSKY_APP_PASSWORD
    })
    res.raise_for_status()
    return res.json()['accessJwt']

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(list(cache), f)

def get_all_mentions(jwt):
    print("🔎 Getting recent mentions...")
    headers = {'Authorization': f'Bearer {jwt}'}
    res = requests.get(f'{BASE_URL}/app.bsky.notification.listNotifications', headers=headers)
    res.raise_for_status()
    notifications = res.json().get('notifications', [])

    cutoff = datetime.utcnow() - timedelta(hours=3)
    recent_mentions = []

    for notif in notifications:
        reason = notif.get('reason')
        uri = notif.get('uri')
        indexed_at = notif.get('indexedAt')
        try:
            notif_time = datetime.strptime(indexed_at, "%Y-%m-%dT%H:%M:%S.%fZ")
        except:
            notif_time = datetime.strptime(indexed_at, "%Y-%m-%dT%H:%M:%SZ")

        if reason == 'mention' and uri and notif_time > cutoff:
            recent_mentions.append(uri)

    return recent_mentions

def find_root_post(thread_node):
    while thread_node.get("parent"):
        thread_node = thread_node["parent"]
    return thread_node["post"]

def get_root_post_uri(mention_uri, jwt):
    print(f"🧵 Getting thread for: {mention_uri}")
    headers = {'Authorization': f'Bearer {jwt}'}
    params = {'uri': mention_uri}
    res = requests.get(f"{BASE_URL}/app.bsky.feed.getPostThread", headers=headers, params=params)
    res.raise_for_status()
    thread_data = res.json()

    try:
        root_post = find_root_post(thread_data["thread"])
        root_uri = root_post["uri"]
        print(f"🌱 Found root post URI: {root_uri}")
        return root_uri
    except Exception as e:
        print(f"❌ 루트 게시글 URI 추출 실패: {e}")
        return None

def get_post_cid(uri, jwt):
    headers = {'Authorization': f'Bearer {jwt}'}
    res = requests.get(f"{BASE_URL}/com.atproto.repo.getRecord", headers=headers, params={
        "repo": uri.split('/')[2],
        "collection": "app.bsky.feed.post",
        "rkey": uri.split('/')[-1]
    })
    res.raise_for_status()
    return res.json()["cid"]

def repost(uri, cid, jwt):
    headers = {
        'Authorization': f'Bearer {jwt}',
        'Content-Type': 'application/json'
    }
    payload = {
        "$type": "app.bsky.feed.repost",
        "subject": {
            "uri": uri,
            "cid": cid
        },
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    res = requests.post(f"{BASE_URL}/com.atproto.repo.createRecord", headers=headers, json={
        "repo": BSKY_HANDLE,
        "collection": "app.bsky.feed.repost",
        "record": payload
    })
    res.raise_for_status()
    print(f"🔁 Reposted: {uri}")

def main():
    jwt = login()
    cache = load_cache()
    mention_uris = get_all_mentions(jwt)

    for mention_uri in mention_uris:
        root_uri = get_root_post_uri(mention_uri, jwt)
        if root_uri and root_uri not in cache:
            try:
                cid = get_post_cid(root_uri, jwt)
                repost(root_uri, cid, jwt)
                cache.add(root_uri)
            except Exception as e:
                print(f"⚠️ 처리 실패: {e}")

    save_cache(cache)

if __name__ == "__main__":
    main()
