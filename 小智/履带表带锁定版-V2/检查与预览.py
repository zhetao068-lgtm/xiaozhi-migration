"""Check assembled solids, export assembly and render an inspection preview."""
from pathlib import Path
import json
import importlib.util
import numpy as np
import trimesh as tm
from matplotlib import pyplot as plt, font_manager
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from 生成模型 import *

def overlap(a,b):
    return round(max(0.,(a^b).volume()),5)

def run():
    p=make()
    base, rear, lid, bolt, cap=[p[k] for k in ('base','rear','lid','bolt','cap')]
    original_back=p['original_back']
    a,b=p['part_a'],p['part_b']
    band=solid(p['band']).translate((0,0,-p['band'].extents[2]/2))
    print('nominal',{'cap/ear':overlap(cap,base),'bolt/ear':overlap(bolt,base),
                    'cap/bolt':overlap(cap,bolt),'new back/lid':overlap(rear,lid),
                    'original back/lid':overlap(original_back,lid)},flush=True)
    report={'nominal_mm3':{'cap_ear':overlap(cap,base),'screw_ear':overlap(bolt,base),
                            'cap_screw':overlap(cap,bolt),
                            'added_geometry_lid':overlap(rear-original_back,lid)}}
    report['pin_variants']={}
    for d,pin in p['bolts'].items():
        approach=[overlap(pin.rotate((360*x/PITCH,0,0)).translate((x,0,0)),base)
                  for x in np.linspace(-5.6,0,57)]
        report['pin_variants'][f'{d:.2f}']={'nominal_radial_clearance_mm':round((BORE-d)/2,3),
                                            'max_install_interference_mm3':max(approach)}
        assert max(approach)<.0005, (d,max(approach))
    report['cap_slide_mm3']={str(round(z,2)):overlap(cap.translate((0,0,z)),base)
                             for z in [0,.15,.4,.8,1,2,3,4,5,6,7,8,9,10]}
    report['captured_screw_mm3']={str(x):overlap(bolt.rotate((360*x/PITCH,0,0)).translate((x,0,0)),cap)
                                 for x in [0,-.24,-.26,-.28,-.32,-.4,-.6,-1.2]}
    assert max(report['nominal_mm3'].values())<.0005,report['nominal_mm3']
    assert report['captured_screw_mm3']['-0.24']==0
    assert report['captured_screw_mm3']['-0.32']>.02
    for side in [-1,1]:
        half=box(-20,-14,-4 if side<0 else 0,0 if side<0 else 4,2.5,5.8)
        one_latch=cap ^ half
        assert overlap(one_latch,base)==0
        assert overlap(one_latch.translate((0,0,.8)),base)>.04
    # Compare substrate engagement with the unchanged prior model. This is geometry,
    # not a prediction of the strength of a printed shell.
    path=HERE.parent/'履带表带锁定版'/'生成模型.py'
    if path.exists():
        spec=importlib.util.spec_from_file_location('prior_geometry',path)
        prior=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prior)
        v1=add(moved(prior.bracket(),1),moved(prior.bracket(),-1),*p['shoes'])-p['trim']
        report['root_overlap_mm3']={'V1':overlap(original_back,v1),'V2':overlap(original_back,p['relieved'])}
        assert report['root_overlap_mm3']['V2']>report['root_overlap_mm3']['V1']
    report['nominal_head_free_travel_mm']=round(HEAD_FACE-CAP_STOP,3)
    print('V2',report['pin_variants'],'head withdrawal',report['captured_screw_mm3'],
          'root engagement',report.get('root_overlap_mm3'),flush=True)
    report['hinge_motion_mm3']={}
    for name,q,s in [('A',a,1),('B',b,-1)]:
        rr={}
        for deg in range(-80,46):
            k=moved(q.rotate((deg,0,0)),s)
            rr[str(deg)]=overlap(k,rear)+overlap(k,lid)+overlap(k,moved(bolt,s))+overlap(k,moved(cap,s))
        report['hinge_motion_mm3'][name]=rr
        print('motion',name,'max interference',max(rr.values()),'samples',len(rr),flush=True)
    # Model axial float at the side clearance limits, leaving 0.02 mm.
    report['axial_offset_max_interference_mm3']={}
    for name,q,s in [('A',a,1),('B',b,-1)]:
        v=[]
        for dx in [-BODY_GAP+.02,BODY_GAP-.02]:
            for deg in range(-80,46,5):
                k=moved(q.rotate((deg,0,0)).translate((dx,0,0)),s)
                v.append(overlap(k,rear)+overlap(k,lid)+overlap(k,moved(bolt,s)))
        report['axial_offset_max_interference_mm3'][name]=max(v)
    assert max(report['axial_offset_max_interference_mm3'].values())<.0005,report
    # Source snap interference is intentional; compare the replacement interface
    # against the same mating pair of unchanged original links.
    orig_a=band.rotate((0,0,180)).translate((0,7.24,0))
    orig_b=band.translate((0,7.24,0))
    next_a=band.rotate((0,0,180)).translate((0,7.24+11.786,0))
    next_b=band.translate((0,7.24+11.786,0))
    report['source_snap_mm3']={'original_A':overlap(orig_a,next_a),'adapted_A':overlap(a,next_a),
                               'original_B':overlap(orig_b,next_b),'adapted_B':overlap(b,next_b)}
    assert all(max(v.values())<.0005 for v in report['hinge_motion_mm3'].values())
    for q,nxt in [(a,next_a),(b,next_b)]:
        assert overlap(q,nxt)<.005
    print('snap',report['source_snap_mm3'],flush=True)
    (HERE/'数字检查.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    objects=[]
    def obj(name,q,color): objects.append((name,q,np.array(color)))
    obj('Modified rear',rear,[.16,.30,.38])
    obj('Original front',lid,[.29,.48,.57])
    for name,q,s in [('A',a,1),('B',b,-1)]:
        obj('Adapter '+name,moved(q,s),[.15,.68,.60])
        obj('Shoulder screw '+name,moved(bolt,s),[.95,.56,.18])
        obj('Locking cap '+name,moved(cap,s),[.96,.71,.27])
        nxt=next_a if s>0 else next_b
        for i in range(3):
            obj(f'Reference link {name}{i+1}',moved(nxt.translate((0,i*11.786,0)),s),
                [.38,.46,.51] if i%2 else [.47,.56,.61])
    scene=tm.Scene()
    for name,q,color in objects:
        m=mesh(q); m.visual.face_colors=tuple(np.r_[color*255,255].astype(int))
        scene.add_geometry(m,node_name=name,geom_name=name)
    (HERE/'装配预览.glb').write_bytes(scene.export(file_type='glb'))
    plate('先打印-三档间隙试装.3mf',[('09',-37,16),('04',-5,16),('05',25,16),
                                     ('10',-48,-13),('06',-33,-13),('11',-18,-13),
                                     ('07',0,-13),('08',22,-13)])
    plate('外壳及连接件-打印盘.3mf',[('01',-40,6),('02',11,8),('03',50,9),
                                     ('04',-50,-44),('05',-23,-44),('06',-2,-44),
                                     ('06',11,-44),('07',25,-44),('07',40,-44)])
    render(objects,a,base,bolt,cap)
    return report

def plate(name, layout):
    # Standard 3MF, with individual parts (and millimeter units) retained for slicers.
    from xml.etree.ElementTree import Element, SubElement, tostring, fromstring
    from zipfile import ZipFile, ZIP_DEFLATED
    model=Element('model',unit='millimeter',xmlns='http://schemas.microsoft.com/3dmanufacturing/core/2015/02')
    resources=SubElement(model,'resources')
    build=SubElement(model,'build')
    meshes=[]
    for i,(prefix,x,y) in enumerate(layout,1):
        paths=list(OUT.glob(prefix+'-*.stl'))
        assert len(paths)==1,paths
        path=paths[0]
        q=tm.load_mesh(path)
        o=SubElement(resources,'object',id=str(i),type='model',name=path.stem)
        m=SubElement(o,'mesh')
        v=SubElement(m,'vertices')
        for a,b,c in q.vertices: SubElement(v,'vertex',x=f'{a:.7f}',y=f'{b:.7f}',z=f'{c:.7f}')
        f=SubElement(m,'triangles')
        for a,b,c in q.faces: SubElement(f,'triangle',v1=str(a),v2=str(b),v3=str(c))
        SubElement(build,'item',objectid=str(i),printable='1',transform=f'1 0 0 0 1 0 0 0 1 {x+85} {y+68} 0')
        meshes.append(q.apply_translation((x+85,y+68,0)))
    with ZipFile(HERE/name,'w',ZIP_DEFLATED) as z:
        z.writestr('3D/3dmodel.model',tostring(model,encoding='utf-8',xml_declaration=True))
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" Target="/3D/3dmodel.model"/></Relationships>')
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
    with ZipFile(HERE/name) as z:
        assert z.testzip() is None
        r=fromstring(z.read('3D/3dmodel.model'))
    assert len(r.findall('./{*}resources/{*}object'))==len(layout)
    assert len(r.findall('./{*}build/{*}item'))==len(layout)
    tm.util.concatenate(meshes).export((HERE/name).with_suffix('.stl'))

def render(objects,a,base,bolt,cap):
    cn=Path('C:/Windows/Fonts/msyh.ttc')
    if cn.exists():
        font_manager.fontManager.addfont(cn)
        plt.rcParams['font.family']=font_manager.FontProperties(fname=cn).get_name()
    fig=plt.figure(figsize=(13.6,8),facecolor='#eaf1f3')
    fig.text(.045,.937,'小智  /  22 mm 履带连接 V2',fontsize=25,weight='bold',color='#122f3b')
    fig.text(.048,.895,'加宽表耳根部   ·   三档光轴配合   ·   双卡舌防退',fontsize=12,color='#45616d')
    def view(bounds,items,e,az,lim):
        ax=fig.add_axes(bounds,projection='3d',facecolor='#eaf1f3')
        for _,q,c in items:
            m=mesh(q); t=m.triangles
            l=np.clip(m.face_normals @ np.array([-.42,-.41,.81]),0,1)
            col=np.clip((.59+.41*l[:,None])*c+(.09*l[:,None]),0,1)
            ax.add_collection3d(Poly3DCollection(t,facecolors=col,edgecolors='none',zsort='average'))
        for axis,l in zip([ax.set_xlim,ax.set_ylim,ax.set_zlim],lim): axis(*l)
        ax.set_box_aspect([h-l for l,h in lim],zoom=1.25); ax.view_init(e,az); ax.set_proj_type('ortho'); ax.set_axis_off()
    view([.025,.13,.57,.72],objects,38,-124,[(-23,22),(-75,75),(-6,21)])
    fig.text(.060,.141,'01  装配状态',fontsize=15,weight='bold',color='#122f3b')
    fig.text(.060,.105,'蓝灰：原壳与加固后盖    青绿：公／母接驳节    金色：防退卡盖',fontsize=10,color='#45616d')
    expl=[('ear',base,[.16,.30,.38]),('adapter',a.translate((0,11,0)),[.15,.68,.60]),
          ('screw',bolt.translate((-14,-8,9)),[.95,.56,.18]),('clip',cap.translate((-8,-3,19)),[.96,.71,.27])]
    view([.56,.24,.41,.57],expl,30,-131,[(-32,17),(-13,27),(-5,26)])
    fig.text(.604,.231,'02  单侧连接件拆解示意',fontsize=15,weight='bold',color='#122f3b')
    fig.text(.604,.189,'接驳节插入 → 肩轴螺丝旋紧 → 卡盖自上滑入',fontsize=10.5,color='#45616d')
    fig.text(.604,.151,'粗牙 Ø4.2 × 1.2 mm   /   默认光轴 Ø4.52 mm',fontsize=10,color='#45616d')
    fig.savefig(HERE/'装配预览.png',dpi=150,facecolor=fig.get_facecolor())
    plt.close(fig)

if __name__=='__main__':
    run()
