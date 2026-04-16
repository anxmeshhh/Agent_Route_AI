with open(r'app\templates\analysis.html', encoding='utf-8') as f:
    content = f.read()

if '_threatTicketId' in content:
    for i,l in enumerate(content.splitlines(),1):
        if '_threatTicketId' in l:
            print(f'STILL FOUND line {i}: {l.strip()[:100]}')
else:
    print('OK: _threatTicketId is completely gone')

if "getReroutes('" in content:
    print('WARNING: old getReroutes() call still present')
else:
    print('OK: old getReroutes() call is gone')
