"""Generate the pinned 22 mm track adapters from the two supplied STL files."""
from pathlib import Path
import numpy as np
import trimesh as tm
from manifold3d import Manifold as M, Mesh, OpType, CrossSection as CS

HERE = Path(__file__).resolve().parent
REF = HERE.parent / '模型参考'
CASE_FILE = REF / '小智ai.stl'
BAND_FILE = REF / '履带表带_V2_22mm.stl'
OUT = HERE / '打印零件'
DY, Z = 27.1, 0.7
PITCH, MAJOR, MINOR = 1.20, 4.20, 3.20
BORE, THREAD_GAP, FLANK_GAP = 4.86, .24, .085
BODY_GAP = .27
SEAT, TIP = -13.1, 16.55
THREAD_START = 11.2

def mesh(a):
    r = a.to_mesh()
    return tm.Trimesh(r.vert_properties[:, :3], r.tri_verts, process=False)

def solid(a):
    r = M(Mesh(np.array(a.vertices,np.float32), np.array(a.faces,np.uint32)))
    assert not r.is_empty(), r.status()
    return r

def add(*args): return M.batch_boolean(args,OpType.Add)
def sub(a,*args): return M.batch_boolean([a,*args],OpType.Subtract)
def box(x0,x1,y0,y1,z0,z1):
    return M.cube((x1-x0,y1-y0,z1-z0)).translate((x0,y0,z0))
def xy(poly,z0,z1):
    return CS([np.array(poly,dtype=float)]).extrude(z1-z0).translate((0,0,z0))
def cyl(a,b,r0,r1=None,n=64):
    return M.cylinder(b-a,r0,r0 if r1 is None else r1,n).rotate((0,90,0)).translate((a,0,0))
def hex_x(a,b,r):
    return M.cylinder(b-a,r,r,6).rotate((0,90,0)).translate((a,0,0))
def hull(*args):
    return M.batch_hull(args)
def moved(a,sign):
    return (a if sign>0 else a.rotate((0,0,180))).translate((0,sign*DY,Z))

def centered(q):
    p=q.copy()
    p.apply_translation(-np.array([*q.bounds.mean(axis=0)[:2],q.bounds[0,2]]))
    return p

def read_refs():
    cover, back, detail = sorted(tm.load_mesh(CASE_FILE).split(), key=lambda q:len(q.faces), reverse=True)
    parts = tm.load_mesh(BAND_FILE).split()
    def target(x,y):
        q=min(parts,key=lambda m:np.linalg.norm(m.bounds.mean(0)[:2]-[x,y]))
        assert np.linalg.norm(q.bounds.mean(0)[:2]-[x,y])<.1
        return q
    band=target(106.898,95.500)
    # Keep the true opposite original snap interfaces for the two belt halves.
    assert np.allclose(band.extents,[21.8,15.67,4.19],atol=.03)
    return list(map(centered,(cover,back,detail,band))), parts

def helix(a,b,clear=0.0,wide=0.0,lead=False,entry=False,shoulder=False):
    """Rounded trapezoid radial profile, single start right-hand screw.
    Uses identical phase for the clearance cutter and male screw."""
    steps=int(np.ceil((b-a)/.032))
    x=np.linspace(a,b,steps+1)
    if shoulder:
        x=np.unique(np.concatenate(([-15.56,SEAT,SEAT+1e-4],np.arange(SEAT+.13,a,.21),x)))
        steps=len(x)-1
    n=80
    t=np.arange(n)*2*np.pi/n
    phase=np.abs(((x[:,None]-THREAD_START)/PITCH-t[None,:]/(2*np.pi)+.5)%1-.5)*PITCH
    tooth=np.clip((.42+wide-phase)/.29,0,1)
    if lead:
        tooth*=np.clip((b-x[:,None])/.72,0,1)*np.clip((x[:,None]-THREAD_START)/.52,0,1)
    r=MINOR/2+clear+(MAJOR-MINOR)/2*tooth
    if shoulder:
        r=np.maximum(r, MINOR/2+(2.2-MINOR/2)*np.clip((THREAD_START+.28-x[:,None])/.33,0,1))
        r[:2,:]=3.50
    if entry:
        r=np.maximum(r,BORE/2*np.clip((THREAD_START+.67-x[:,None])/.62,0,1)
                     +(MINOR/2+clear)*np.clip((x[:,None]-THREAD_START-.05)/.62,0,1))
    vs=np.stack(np.broadcast_arrays(x[:,None],r*np.cos(t),r*np.sin(t)),axis=-1).reshape(-1,3)
    vs=np.vstack([vs,[x[0],0,0],[x[-1],0,0]])
    fs=[]
    for i in range(steps):
        for j in range(n):
            p=i*n+j; q=i*n+(j+1)%n
            fs.extend([(p,q,p+n),(q,q+n,p+n)])
    for j in range(n):
        k=(j+1)%n
        fs.extend([(len(vs)-2,k,j),(len(vs)-1,steps*n+j,steps*n+k)])
    return solid(tm.Trimesh(vs,fs,process=False))

def screw():
    shaft=helix(THREAD_START-.20,TIP,lead=True,shoulder=True)
    return shaft-hex_x(-15.68,-13.84,1.76)

def ear_blank():
    # Diagonal cap rails sit around the recessed head. Their channels are open on top.
    near=hull(cyl(-15.8,-11.22,4.40),
              box(-15.75,-12.1,-5.00,5.54,-3.45,5.25))
    mid=cyl(-3.88,3.88,3.55)
    far=cyl(11.22,17.40,3.7)
    # Broad pad on the unperforated edge of the back; exterior slope clears the cover.
    pad=hull(box(-14.8,14.8,-13.45,-8.0,-3.85,-.40),
             box(-13.8,13.75,-12.8,-7.52,-.42,-.14))
    # Single underside bridge; its top rises only outside the case sweep.
    bridge=hull(box(-14.72,14.72,-8.30,-7.3,-3.85,-1.38),
                box(-15.6,16.80,-2.6,-2.36,-3.30,-1.12))
    # Local cheeks connect the bridge to the three journals, without spanning the belt sweep.
    roots=[hull(box(a+.12,b-.12,-3.15,-2.45,-3.24,-1.48),
                box(a+.12,b-.12,-4.0,-2.4,-2.60,-.82),
                box(a+.12,b-.12,-2.30,-1.82,-2.73,-.80))
           for a,b in [(-15.8,-11.22),(-3.88,3.88),(11.22,17.40)]]
    return add(near,mid,far,pad,bridge,*roots)

def bracket():
    raw=ear_blank()
    # A blind thread cavity prevents the screw tip from touching skin or the next link.
    thread=helix(THREAD_START-.10,TIP+.13,THREAD_GAP,FLANK_GAP,entry=True)
    rails=xy([(-16.4,-4.44),(-15.82,-4.44),(-14.77,-5.16),
              (-14.77,5.16),(-15.82,4.44),(-16.4,4.44)],-3.62,6.5)
    catch=box(-15.01,-14.21,2.13,3.68,3.17,4.25)
    a=raw-cyl(-16.3,SEAT+.002,3.79)
    a-=add(cyl(-13.13,THREAD_START-.03,BORE/2+.003),thread)
    a=sub(a,rails,catch)
    return sub(a,cyl(-11.219,-3.881,3.64),cyl(3.881,11.219,3.64))

def clip():
    base=hull(box(-17.15,-15.97,-4.28,4.28,-3.43,5.51),
              box(-16.86,-15.97,-4.28,4.28,5.48,6.03))
    # Separate rails leave the center of the cap above the screw head.
    rail=xy([(-16.19,3.90),(-15.79,3.91),(-14.99,4.05),
             (-14.99,4.91),(-15.80,4.34),(-16.19,4.15)],-3.399,5.02)
    main=add(base,rail,rail.mirror((0,1,0)))
    # U slot creates a leaf in the plate; a screwdriver can retract it outward.
    for y0,y1 in [(1.40,1.86),(3.57,4.02)]:
        main-=box(-17.4,-15.74,y0,y1,-2.22,4.55)
    main-=box(-17.4,-15.74,1.40,4.02,4.12,4.55)
    main-=box(-16.27,-15.88,1.86,3.57,-1.96,4.13)
    barb=hull(box(-16.48,-15.88,2.28,3.45,3.26,3.36),
              box(-16.48,-14.45,2.28,3.45,3.98,4.105))
    return add(main,barb)

def adapter(band,kind):
    # Keep original geometry on the outgoing side; both inputs share the same new hinge.
    # A retains the original double male; B retains the original triple female.
    s=-1 if kind=='A' else 1
    q=band.copy()
    if s<0: q.apply_transform(tm.transformations.rotation_matrix(np.pi,[0,0,1]))
    q.apply_translation((0,7.24,-q.extents[2]/2))
    native=solid(q).simplify(.003) ^ box(-12,12,5.28,16,-4,4)
    # Chamfered shoulder and tapered root into the native link.
    anchor=hull(box(-10.52,10.52,5.32,6.07,-1.96,1.96),
                box(-9.02,9.02,3.83,4.04,-2.32,2.32))
    lobes=[hull(cyl(a,b,3.26),box(a,b,2.63,4.33,-1.82,1.82))
           for a,b in [(-9.73,-3.88-BODY_GAP),
                       (3.88+BODY_GAP,9.73)]]
    shape=sub(add(native,anchor,*lobes),cyl(-10.0,10.0,BORE/2)).simplify(.002)
    # Submicron-volume shells in the tessellated snap dimples have no printable material.
    components=shape.decompose()
    main=max(components,key=lambda c:c.volume())
    assert all(c is main or abs(c.volume())<1e-5 for c in components)
    return main

def save_stl(a,name):
    m=mesh(a) if isinstance(a,M) else a.copy()
    m.apply_translation((-m.bounds.mean(0)[0],-m.bounds.mean(0)[1],-m.bounds[0,2]))
    m.export(OUT/(name+'.stl'))
    reread=tm.load_mesh(OUT/(name+'.stl'))
    assert reread.is_volume and len(reread.split())==1, (name,'invalid or disconnected STL')
    return m

def make():
    OUT.mkdir(exist_ok=True)
    (cover,back,detail,band),original_parts=read_refs()
    original_back=solid(back)
    base=bracket()
    # Tie both pads into the existing bottom without adding material inside the case.
    # The two ribs below are part of the back, so the hinge load bypasses the lid.
    shoes=[]
    for s in [-1,1]:
        shoe=hull(box(-13.65,13.65,-13.42,-8.13,-2.15,-.18),
                  box(-13.85,13.85,-13.25,-7.90,-.24,-.20))
        shoes.append(moved(shoe,s))
    lid=solid(cover).rotate((180,0,0)).translate((-.85,0,19.0))
    # Relieve around the existing lid's lower edge before fusing the two brackets.
    added=add(moved(base,1),moved(base,-1),*shoes)
    trim=lid ^ box(-25,25,-23,23,-4,-.02)
    relieved=added-trim
    rear=add(original_back,relieved)
    assert len(rear.decompose())==1, [c.bounding_box() for c in rear.decompose()]
    part_a,part_b=adapter(band,'A'),adapter(band,'B')
    bolt,cap=screw(),clip()
    tip_parts=[('01-改造后盖',rear),('02-原面壳',cover),('03-原独立小件',detail),
               ('04-公扣接驳节',part_a),('05-母扣接驳节',part_b),
               ('06-肩轴螺丝-打印2件',bolt.rotate((0,-90,0))),
               ('07-防退卡盖-打印2件',cap.rotate((0,-90,0))),
               ('08-原标准链节-按腕围选用',band)]
    # Same-fit test: one lug set cut from the model, without committing to the whole case.
    coupon=(base ^ box(-17,18,-6,6.1,-4.6,6.5))
    assert len(coupon.decompose())==1
    tip_parts.append(('09-表耳试装片',coupon))
    for name,q in tip_parts: save_stl(q,name)
    return locals()

if __name__=='__main__':
    make()
