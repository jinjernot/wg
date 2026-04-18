import os, json

bad_files = []
for f in os.listdir('data/logs/trades'):
    if not f.endswith('.json'):
        continue
    path = f'data/logs/trades/{f}'
    try:
        data = open(path, 'r').read()
        json.loads(data)
    except Exception as e:
        print(f"Error in {f}: {e}")
        bad_files.append(f)

if not bad_files:
    print("All JSON files are valid right now.")
