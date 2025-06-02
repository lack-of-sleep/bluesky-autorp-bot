import os
import time
import requests

# GitHub Secrets에서 불러오는 핸들과 앱 패스워드
HANDLE = os.getenv("BSKY_HANDLE")
APP_PASSWORD = os.getenv("BSKY_APP_PASSWORD")

# 블루스카이 RP연동
BASE_URL = 'https://bsky.social/xrpc'

# 로그인 함수
def login():
    res = requests.post(
        f'{BASE_URL}/com.atproto.server.createSession',
        json={'identifier': HANDLE, 'password': APP_PASSWORD}
    )
    res.raise_for_status()
    data = res.json()
    return data['accessJwt'], data['did']

# 최신 멘션 가져오기
def get_latest_mention(jwt):
    headers = {'Authorization': f'Bearer {jwt}'}
    res = requests.get(f'{BASE_URL}/app.bsky.notification.listNotifications', headers=headers)
    res.raise_for_status()
    notifications = res.json().get('notifications', [])
    
    for notif in notifications:
        reason = notif.get('reason')
        uri = notif.get('uri')
        print(f"🔔 Notification: {reason} - {uri}")
        if reason == 'mention' and uri:
            return uri
    return None

# 루트 포스트 찾기
def get_root_post(jwt, uri):
    headers = {'Authorization': f'Bearer {jwt}'}
    res = requests.get(
        f"{BASE_URL}/app.bsky.feed.getPostThread",
        headers=headers,
        params={'uri': uri}
    )
    res.raise_for_status()
    thread = res.json().get('thread', {})

    post = thread.get('post')
    while post and 'parent' in post:
        post = post['parent']
    return post['uri'], post['cid'] if post else (None, None)

# 리포스트 함수
def repost(jwt, did, uri, cid):
    headers = {'Authorization': f'Bearer {jwt}'}
    record = {
        "repo": did,
        "collection": "app.bsky.feed.repost",
        "record": {
            "$type": "app.bsky.feed.repost",
            "subject": {
                "uri": uri,
                "cid": cid
            },
            "createdAt": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }
    }
    res = requests.post(f'{BASE_URL}/com.atproto.repo.createRecord', headers=headers, json=record)
    return res.status_code == 200

# 메인 실행 함수
def run_bot():
    print("🔐 Logging in...")
    jwt, did = login()
    
    print("🔎 Getting latest mention...")
    mention_uri = get_latest_mention(jwt)
    if not mention_uri:
        print("❌ No mention found.")
        return

    print(f"📍 Mentioned URI: {mention_uri}")
    root_uri, root_cid = get_root_post(jwt, mention_uri)
    
    if root_uri and root_cid:
        print(f"📢 Reposting root URI: {root_uri}")
        if repost(jwt, did, root_uri, root_cid):
            print("✅ Repost successful!")
        else:
            print("❌ Repost failed.")
    else:
        print("⚠️ Could not find root post.")

# 엔트리포인트
if __name__ == "__main__":
    run_bot()
