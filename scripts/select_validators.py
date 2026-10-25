import urllib.request
import json

url = 'https://www.validators.app/api/v1/validators/mainnet.json?limit=1000'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=15) as resp:
    data = json.loads(resp.read().decode('utf-8'))

selected = {}
targets = ['4.3.2', '26.10.4', '4.5.0', '0.1.1', '3.1.8']
for v in data:
    ver = v.get('software_version')
    if ver in targets:
        if ver not in selected:
            selected[ver] = []
        if len(selected[ver]) < 3:
            selected[ver].append({
                'name': v.get('name'),
                'version': ver,
                'vote_account': v.get('vote_account'),
                'node_pubkey': v.get('account'),
                'active_stake': v.get('active_stake')
            })

print(json.dumps(selected, indent=2))
