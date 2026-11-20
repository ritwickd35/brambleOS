from load import *
from collections import Counter,defaultdict
def basef(i): return 0 if i<8 else 0xb00 if i==30 else 0xe00 if i>=31 and i<34 else 0x500
def norm(w): # normalize branch targets to relative
    return w
subs=defaultdict(list)
for i,p in enumerate(P):
    b=basef(i)
    tg=sorted(set((w&0xfff)-b for w in p if w>>24==0xae and (w>>16)&255==6))
    for t in tg:
        # body to first ae0a
        k=t
        while k<len(p) and not (p[k]>>24==0xae and (p[k]>>16)&255==0xa): k+=1
        body=p[t:k+1]
        # normalize djnz target relative
        nb=tuple(((w&0xffff0000)|(((w&0xfff)-b-t)&0xffff)) if (w>>24) in (0xa1,0xa4,0xaa) and ((w>>16)&255)==4 else w for w in body)
        subs[nb].append((i,t))
print(len(subs))
for nb,uses in sorted(subs.items(),key=lambda x:-len(x[1])):
    print(len(nb),len(uses),[ (NAMES[i],hex(t)) for i,t in uses[:3]], ' '.join('%08x'%w for w in nb[:6]))
