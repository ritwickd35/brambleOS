from load import *
from dis import dis
def basef(i): return 0 if i<8 else 0xb00 if i==30 else 0xe00 if 31<=i<34 else 0x500
import sys
def kind(p,t):
    # classify sub at relative t
    k=t
    n=0
    while k<len(p) and not(p[k]>>24==0xae and (p[k]>>16)&255==0xa): k+=1
    n=k-t+1
    return n
for i,p in enumerate(P):
    b=basef(i);out=[]
    for j,w in enumerate(p):
        op=w>>24;b1=(w>>16)&255
        if op==0xae and b1==6: out.append('CALL(%d)'%kind(p,(w&0xfff)-b))
        elif op==0x20: out.append({0:'cp',3:'v3',7:'vv',8:'vs',0xd:'cp40'}.get(b1,'v%x'%b1))
        elif op==0xa0 and b1==8: out.append('JMP%+d'%(((w&0xfff)-b)-j))
        elif op==0xae and b1==0xa: out.append('RET')
        elif op==0xa0 and b1==0xe: out.append('HALT')
        elif (op&0xf0)==0xa0 and b1==4: out.append('LOOP%x(%d)'%(op&15,j-((w&0xfff)-b)+1))
    print(i,NAMES[i],' '.join(out))
