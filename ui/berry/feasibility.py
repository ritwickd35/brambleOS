# Berry style at real resolution (160x128, RGB565-quantised): gradient (plain vs dithered), tiles, sheen, glow, a pedal
import numpy as np
from PIL import Image
W,H=160,128
def q565(a):                                    # what the panel can show
    a=a.astype(float); r=np.round(a[...,0]/255*31)*255/31; g=np.round(a[...,1]/255*63)*255/63; b=np.round(a[...,2]/255*31)*255/31
    return np.stack([r,g,b],-1).clip(0,255).astype(np.uint8)
top,bot=np.array([42,14,40]),np.array([16,5,18])   # plum -> very dark wine
t=np.linspace(0,1,H)[:,None,None]; grad=(top*(1-t)+bot*t)*np.ones((1,W,1))
bayer=np.array([[0,2],[3,1]])/4-0.375
dith=grad+np.tile(bayer,(H//2,W//2))[...,None]*(255/31)     # 2x2 ordered dither, one 565 step
img=np.where(np.arange(W)[None,:,None]<80, q565(grad), q565(dith)).astype(float)
def tile(img,x,y,w,h,base,lit,glow=None):
    yy,xx=np.mgrid[0:h,0:w]; r=3
    inside=np.ones((h,w),bool)
    for cx,cy in ((r,r),(w-1-r,r),(r,h-1-r),(w-1-r,h-1-r)):
        m=((xx<r)|(xx>w-1-r))&((yy<r)|(yy>h-1-r)); inside&=~(m&((xx-cx)**2+(yy-cy)**2>r*r))
    c=np.array(base,float)*(1.0 if lit else 0.45)
    face=c*(1.08-0.16*yy/h)[...,None]                         # soft vertical sheen
    rim_hi=inside&((yy==0)|(xx==0)); rim_lo=inside&((yy==h-1)|(xx==w-1))
    out=img[y:y+h,x:x+w]
    out[inside]=face[inside]; out[rim_hi]=np.minimum(c*1.6+20,255); out[rim_lo]=c*0.55
    if glow is not None:
        g=np.array(glow,float)
        for d in (1,2):
            ring=np.zeros((h+2*d,w+2*d),bool); ring[0,:]=ring[-1,:]=ring[:,0]=ring[:,-1]=True
            sl=img[y-d:y+h+d,x-d:x+w+d]; sl[ring]=sl[ring]*0.4+g*(0.6 if d==1 else 0.3)
def pedal(img,x,y,body):
    b=np.array(body,float)
    for yy in range(22):
        for xx in range(18):
            if (xx in (0,17) and yy in (0,21)): continue
            v=b*(1.15-0.3*yy/22); 
            if yy==0 or xx==0: v=np.minimum(b*1.5+30,255)
            if yy==21 or xx==17: v=b*0.5
            img[y+yy,x+xx]=v
    for kx in (4,9,14):
        img[y+3:y+6,x+kx-1:x+kx+1]=[235,235,230]; img[y+3,x+kx-1]=[255,255,255]
    img[y+10:y+13,x+4:x+14]=[250,248,240]; img[y+15:y+19,x+6:x+12]=[150,150,155]; img[y+15,x+6:x+12]=[200,200,205]
tile(img,8,40,28,24,(70,160,90),True,glow=(230,170,255)); pedal(img,13,41,(40,150,70))
tile(img,44,40,28,24,(70,160,90),False); pedal(img,49,41,(40,150,70)*np.array(0.45))
tile(img,88,40,28,24,(200,140,60),True); tile(img,124,40,28,24,(120,60,150),True)
img[100:104,8:60]=q565(np.ones((4,52,3))*[60,170,90]); img[100:104,88:150]=q565(np.ones((4,62,3))*[200,40,70])
im=Image.fromarray(q565(img)); im.save("ui/berry/feasibility_1x.png"); im.resize((W*4,H*4),Image.NEAREST).save("ui/berry/feasibility_4x.png")
print("ok")
