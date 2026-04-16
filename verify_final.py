with open(r'app\templates\analysis.html', encoding='utf-8') as f:
    lines = f.readlines()

checks = {'genUUID':[],'fillExample':[],'THREAT_ICONS':[],'switchSimMode':[],'_currentThreat':[]}
for i,l in enumerate(lines,1):
    for k in checks:
        if k in l and ('function ' in l or 'const ' in l or 'let ' in l):
            checks[k].append(i)

print('=== Declaration counts (should be 1 each) ===')
for k,v in checks.items():
    status = 'OK' if len(v)==1 else f'PROBLEM ({len(v)} times at {v})'
    print(f'  {k}: {status}')

print('\n=== Key functions present ===')
for fn in ['switchSimMode','clearThreat','induceThreatFromPanel','genReroutesFromPanel',
           'renderThreatCard','renderReroutes','backToBoard','loadTickets',
           'runTicketAnalysis','viewTicketResult']:
    found = any(('function '+fn) in l for l in lines)
    print(f'  {fn}: {"OK" if found else "MISSING"}')
