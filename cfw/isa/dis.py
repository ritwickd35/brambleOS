"""Hypothesis disassembler for Sonicake Pocket Master engine programs.
word = [op:8][b1:8][imm:16]; op = class<<4 | R ; b1 = A<<4 | sub (reg-reg classes)"""
from load import *
import struct
def f32(h,l=0): return struct.unpack('<f',struct.pack('<I',((h&0xffff)<<16)|l))[0]
def dis(w,pc,base=0):
    c=w>>28;R=(w>>24)&15;b1=(w>>16)&255;A=b1>>4;S=b1&15;imm=w&0xffff
    if w==0: return 'nop?/pad'
    if c==2: return {0:'copyv r11<-r9[r10]',3:'op20.3',7:'vmulv r11=r9*[r8..] n=r10',8:'vmuls r11=r9*r8(f) n=r10',0xd:'copyv r8<-r9 n=r10'}.get(S,'op20.%x'%S)
    if c==5: return ('ld r%d,[0x%x]' if b1==8 else 'st [0x%x],r%d' if b1==0 else '5?')%((R,imm) if b1==8 else (imm,R))
    if c==7:
        if b1==6: return 'mov r%d,#0x%x'%(R,imm)
        if b1==0xc6: return 'movhi r%d,#0x%04x (f=%g)'%(R,imm,f32(imm))
        if b1==0x86: return 'movlo r%d,#0x%04x'%(R,imm)
        if b1==0: return 'add r%d,#%d'%(R,imm)
        if b1==0xc8: return 'movhi.q r%d,#0x%04x'%(R,imm)
        return '7?%02x r%d,#%x'%(b1,R,imm)
    if c==8: return '%s r%d,r%d,r%d  [sub=%x]'%({6:'fmul',0xa:'fmac'}.get(S,'8op'),R,A,imm&15,S)
    if c==0xc: return 'c-%x r%d,r%d,r%d imm=%04x'%(S,R,imm&15,A,imm)
    if c==0xe: return {2:'ld r%d,[r%d]',3:'ld r%d,[r%d]++',4:'st [r%d],r%d',5:'st [r%d]++,r%d'}[S]%((R,A) if S<4 else (R,A)) if S in(2,3,4,5) else 'e?'
    if c==0xf: return 'f%x r%d,r%d imm=%x'%(S,R,A,imm) 
    if c==0xa:
        if R==0xe and False: pass
        return {4:'djnz r%d,0x%x',6:'call 0x%x',8:'jmp 0x%x',0xa:'ret'}.get(S,'a?')%((R,imm&0xfff) if S==4 else (imm&0xfff,) if S in(6,8) else ())
    if c==9: return '9%x r%d b1=%02x imm=%04x'%(R,R,b1,imm)
    return '?%08x'%w
if __name__=='__main__':
    import sys
    i=int(sys.argv[1]);b=0 if i<8 else 0x500 if i<30 or i==34 else 0xb00 if i==30 else 0xe00
    for j,w in enumerate(P[i]): print('%04x %08x  %s'%(j+b,w,dis(w,j,b)))
