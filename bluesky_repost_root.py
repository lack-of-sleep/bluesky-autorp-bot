import requests
import json
import os
import time

BASE_URL = "https://bsky.social/xrpc"
BSKY_HANDLE = os.getenv("BSKY_HANDLE")
BSKY_APP_PASSWORD = os.getenv("BSKY_APP_PASSWORD")

def login():
    print("🔐 Logging in...")
    res = requests.post(f"{BASE_URL}/com.atproto.server.createSession", json={
        "identifier": BSKY_HANDLE,
        "password": BSKY_APP_PASSWORD
    })
    res.raise_for_status()
    return res.json()['accessJwt']

def get_latest_mention(jwt):
    print("🔎 Getting latest mention...")
    headers = {'Authorization': f'Bearer {jwt}'}
    res = requests.get(f'{BASE_URL}/app.bsky.notification.listNotifications', headers=headers)
    res.raise_for_status()
    notifications = res.json().get('notifications', [])

    for notif in notifications:
        reason = notif.get('reason')
        uri = notif.get('uri')
        print(f"📨 Notification: reason={reason}, uri={uri}")
        if reason == 'mention' and uri:
            return uri
    return None

def find_root_post(thread_node):
    """스레드 구조에서 루트 포스트까지 거슬러 올라가는 함수"""
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
        "rkey": uri.split('/')[-1],
    })
    res.raise_for_status()
    return res.json()['cid']

def repost(uri, jwt):
    print(f"🔁 Reposting: {uri}")
    headers = {'Authorization': f'Bearer {jwt}'}
    data = {
        "repo": BSKY_HANDLE,
        "collection": "app.bsky.feed.repost",
        "record": {
            "$type": "app.bsky.feed.repost",
            "subject": {
                "uri": uri,
                "cid": get_post_cid(uri, jwt)
            },
            "createdAt": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }
    }
    res = requests.post(f"{BASE_URL}/com.atproto.repo.createRecord", headers=headers, json=data)
    res.raise_for_status()
    print("✅ Repost complete")

def run_bot():
    jwt = login()
    mention_uri = get_latest_mention(jwt)
    if mention_uri:
        root_uri = get_root_post_uri(mention_uri, jwt)
        if root_uri:
            repost(root_uri, jwt)
        else:
            print("⚠️ 루트 URI 없음, 리포스트 생략")
    else:
        print("⚠️ mention 없음")

if __name__ == "__main__":
    run_bot()
