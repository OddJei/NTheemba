#!/usr/bin/env python3
import json
import sys
import redis

STREAM_REQUESTS = 'intent:requests'
STREAM_RESULTS = 'intent:results'
STREAM_DLQ = 'intent:dlq'
CONSUMER_GROUP = 'intent-workers'

r = redis.Redis.from_url('redis://localhost:6379/0', decode_responses=True)

print('Connected to Redis OK')

# Requests overview
try:
    print('\n=== intent:requests ===')
    print('XLEN:', r.xlen(STREAM_REQUESTS))
    recent = r.xrevrange(STREAM_REQUESTS, count=50)
    print('Last', len(recent), 'entries:')
    for _id, fields in recent:
        evt = None
        payload = fields.get('payload') if isinstance(fields, dict) else None
        if payload:
            try:
                p = json.loads(payload)
                evt = p.get('event_id')
            except Exception:
                evt = None
        # fallback
        evt = evt or fields.get('event_id') or ''
        print(' ', _id, evt, 'attempts=' + str(fields.get('attempts', '')))
except Exception as e:
    print('Error reading intent:requests:', e)

# XPENDING summary & list
try:
    print('\n=== XPENDING summary ===')
    try:
        summary = r.execute_command('XPENDING', STREAM_REQUESTS, CONSUMER_GROUP)
        print('XPENDING summary raw:', summary)
    except Exception as e:
        print('XPENDING summary failed:', e)

    try:
        pend = r.execute_command('XPENDING', STREAM_REQUESTS, CONSUMER_GROUP, '-', '+', 100)
        print('XPENDING entries count:', len(pend))
        for item in pend:
            # item usually [id, consumer, ms_since_idle, deliveries]
            print(' ', item)
    except Exception as e:
        print('XPENDING range failed:', e)
except Exception as e:
    print('XPENDING check error:', e)

# DLQ
try:
    print('\n=== intent:dlq (last 20) ===')
    dlq = r.xrange(STREAM_DLQ, count=20)
    print('DLQ entries:', len(dlq))
    for _id, fields in dlq:
        print(' ', _id, fields.get('event_id'), fields.get('error'))
except Exception as e:
    print('Error reading DLQ:', e)

print('\nDone')
