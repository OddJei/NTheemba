import redis
r = redis.Redis.from_url('redis://localhost:6379/0', decode_responses=True)
entries = r.xrange('intent:results', count=10)
if not entries:
    print('no entries')
else:
    for id, fields in entries:
        print('ID=', id)
        for k, v in fields.items():
            if isinstance(v, str) and len(v) > 400:
                print(' ', k, '->', v[:400] + '...')
            else:
                print(' ', k, '->', v)
