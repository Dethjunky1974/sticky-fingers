from PIL import Image, ImageDraw, ImageFont
import numpy as np

BG=(0x9C,0xB4,0x74); INK=(0x0E,0x1A,0x09)
CELL=10          # screen px per LCD cell
GAP=1            # 1px LCD gap between cells (Snake-title look)
W=128            # grid width in cells

# ---------- hands: sample the Nokia screenshot on its 7px LCD grid
im=Image.open('nokia.png').convert('L'); a=np.array(im).astype(int); h,w=a.shape
P=7
best=None
for ox in range(P):
    for oy in range(P):
        xs=np.arange(ox+P//2,w,P); ys=np.arange(oy+P//2,h,P)
        s=a[np.ix_(ys,xs)]
        # crispness: fraction of samples far from mid-grey
        score=np.mean((s<60)|(s>140))
        if best is None or score>best[0]: best=(score,ox,oy)
score,ox,oy=best
xs=np.arange(ox+P//2,w,P); ys=np.arange(oy+P//2,h,P)
grid=(a[np.ix_(ys,xs)]<100)
# rows of the hands band (y 19..335) -> cell rows
r0=max(0,(19-oy)//P); r1=min(grid.shape[0],(335-oy)//P+1)
hands=grid[r0:r1]
# trim empty columns
cols=np.where(hands.any(axis=0))[0]; hands=hands[:,cols[0]:cols[-1]+1]
rows=np.where(hands.any(axis=1))[0]; hands=hands[rows[0]:rows[-1]+1]
print('grid phase',ox,oy,'crispness %.3f'%score,'hands cells',hands.shape)

# ---------- text rasterised to cells
def text_cells(txt, fontfile, cap_cells, max_w, tracking=0, weight=0.0):
    # find a font size whose rendered cap height == cap_cells
    for size in range(20,600):
        f=ImageFont.truetype(fontfile,size)
        bb=f.getbbox('H'); capH=bb[3]-bb[1]
        if capH>=cap_cells*CELL: break
    # render big, then downsample to cells by area threshold
    parts=[]
    total=0
    for ch in txt:
        bb=f.getbbox(ch); parts.append((ch,bb)); total+=bb[2]-bb[0]
    tr=int(round(tracking*CELL))
    widthpx=total+tr*(len(txt)-1)+int(weight*CELL*2)
    img=Image.new('L',(widthpx+CELL*2,capH+CELL*2),0); d=ImageDraw.Draw(img)
    x=CELL
    for ch,bb in parts:
        d.text((x-bb[0],CELL-bb[1]),ch,font=f,fill=255,stroke_width=int(weight*CELL),stroke_fill=255); x+=bb[2]-bb[0]+tr
    arr=np.array(img)
    ch_,cw_=arr.shape[0]//CELL, arr.shape[1]//CELL
    cells=arr[:ch_*CELL,:cw_*CELL].reshape(ch_,CELL,cw_,CELL).mean(axis=(1,3))>110
    rows=np.where(cells.any(axis=1))[0]; cols=np.where(cells.any(axis=0))[0]
    cells=cells[rows[0]:rows[-1]+1, cols[0]:cols[-1]+1]
    if cells.shape[1]>max_w:
        return text_cells(txt,fontfile,cap_cells-1,max_w,tracking,weight)
    return cells

sticky=text_cells('STICKY','Bangers.ttf',cap_cells=21,max_w=116,tracking=0.5,weight=0.8)
fingers=text_cells('FINGERS','Michroma.ttf',cap_cells=12,max_w=118,tracking=1.0,weight=0.4)
print('STICKY cells',sticky.shape,'FINGERS cells',fingers.shape)

# ---------- compose on one LCD
M=5; G1=3; G2=5
Hc=M+sticky.shape[0]+G1+hands.shape[0]+G2+fingers.shape[0]+M
canvas=np.zeros((Hc,W),bool)
def blit(cells,y): x=(W-cells.shape[1])//2; canvas[y:y+cells.shape[0],x:x+cells.shape[1]]|=cells
y=M; blit(sticky,y); y+=sticky.shape[0]+G1; blit(hands,y); y+=hands.shape[0]+G2; blit(fingers,y)
print('canvas cells',canvas.shape,'->',W*CELL,'x',Hc*CELL)

out=Image.new('RGB',(W*CELL,Hc*CELL),BG); d=ImageDraw.Draw(out)
ys,xs=np.where(canvas)
for cy,cx in zip(ys,xs):
    d.rectangle([cx*CELL,cy*CELL,cx*CELL+CELL-1-GAP,cy*CELL+CELL-1-GAP],fill=INK)
out.save('hero.png'); print('saved hero.png',out.size)
