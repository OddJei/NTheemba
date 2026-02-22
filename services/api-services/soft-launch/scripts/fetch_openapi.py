import urllib.request, json
u='http://localhost:8500/openapi.json'
try:
    with urllib.request.urlopen(u, timeout=5) as r:
        b=r.read().decode()
        j=json.loads(b)
        print('Title:', j.get('info',{}).get('title'))
        print('Security:', j.get('security'))
        print('Components securitySchemes keys:', list(j.get('components',{}).get('securitySchemes',{}).keys()))
        print('\nSample path /internal/businesses security:')
        import pprint
        pprint.pprint(j.get('paths',{}).get('/internal/businesses'))
except Exception as e:
    print('Failed to fetch/openapi:', repr(e))
