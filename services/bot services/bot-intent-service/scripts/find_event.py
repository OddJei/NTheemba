#!/usr/bin/env python3
import sys, json
import redis

def main(event_id: str):
    r = redis.Redis.from_url('redis://localhost:6379/0', decode_responses=True)
    entries = r.xrange('intent:results', count=200)
    if not entries:
        print('no entries')
        return 1
    for _id, fields in reversed(entries):
        payload = fields.get('payload')
        try:
            obj = json.loads(payload)
        except Exception:
            continue
        if obj.get('event_id') == event_id:
            print('ID=', _id)
            print(json.dumps(obj, indent=2, ensure_ascii=False))
            return 0
    print(f'event {event_id} not found in last {len(entries)} entries')
    return 2

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: find_event.py <event_id>')
        sys.exit(3)
    sys.exit(main(sys.argv[1]))
