"""Scrollable native decoration toggles in the separate operator window."""
from direct.gui.DirectGui import DirectScrolledFrame, DirectCheckButton
from direct.gui import DirectGuiGlobals as DGG
from .text import display_text


def scenery_category(key):
    """Classify both Classic and namespaced scene-study placement identities."""
    if not key.startswith('reef:'):return None
    kind=key.removeprefix('reef:').removeprefix('study:').split(':')[0]
    return 'Plants' if kind in ('plant','grass') else 'Reef'


def scenery_name(key):
    if not key.startswith('reef:study:'):
        return key.removeprefix('reef:').replace(':',' ').title()
    kind,_,index=key.removeprefix('reef:study:').partition(':')
    name={'rock':'Limestone','distant':'Distant reef','plate':'Plate coral',
          'fan':'Sea fan','sponge':'Tube sponge','colony':'Coral colony',
          'grass':'Seagrass','rubble':'Reef pebble'}.get(kind,kind.title())
    return f'{name} {int(index)+1}' if index.isdigit() else name


class DecorationPanel:
    def __init__(self,controls,parent):
        self.controls,self.app=controls,controls.app
        self.category="Library";self.checks={};self.status_labels={}
        controls.label(parent,"SEABED LIBRARY",18,105,12)
        for name,x in (("Library",18),("Reef",150),("Plants",288)):
            controls.button(parent,name,x,135,126,lambda n=name:self.choose(n))
        self.scroller=DirectScrolledFrame(parent=parent,frameSize=(0,396,-365,0),
            canvasSize=(0,372,-365,0),pos=(18,0,-170),scrollBarWidth=14,
            frameColor=(.025,.095,.115,1),autoHideScrollBars=True,
            horizontalScroll_scrollSize=0,verticalScroll_scrollSize=.15)
        self.rows=[]
        controls.button(parent,"Refresh library",18,556,154,self.refresh)
        self.note=controls.label(parent,"",18,584,11,396)
        self.rebuild()

    def choose(self,name):
        self.category=name;self.rebuild();self.scroller.verticalScroll["value"]=0

    def rebuild(self):
        for row in self.rows:row.destroy()
        self.rows=[];self.checks={};self.status_labels={}
        if self.category!="Library":
            self.rebuild_scenery();return
        library=self.app.decorations
        height=max(365,len(library.items)*74+12)
        self.scroller["canvasSize"]=(0,372,-height,0)
        canvas=self.scroller.getCanvas()
        for i,item in enumerate(library.items.values()):
            available=item.key in library.nodes
            check=DirectCheckButton(parent=canvas,text=display_text(item.name),text_align=0,
                text_scale=14,text_pos=(24,0),text_fg=(.86,.94,.89,1),
                indicatorValue=library.enabled(item) if available else False,
                indicator_scale=12,indicator_pos=(6,0,4),
                frameColor=(0,0,0,0),relief=None,pos=(8,0,-25-i*74),
                command=self.toggle,extraArgs=[item.key],state=DGG.NORMAL if available else DGG.DISABLED)
            self.rows.append(check)
            self.rows.append(self.controls.label(canvas,display_text(item.description),32,49+i*74,11,328))
        self.note["text"]=display_text((library.errors[0][:110] if library.errors else
            f"{len(library.items)} objects · tank/assets/decorations/"))

    def rebuild_scenery(self):
        records={k:r for k,r in self.app.scenery_objects.records.items() if scenery_category(k)==self.category}
        self.scroller['canvasSize']=(0,372,-max(365,len(records)*55+12),0)
        for i,(key,record) in enumerate(records.items()):
            check=DirectCheckButton(parent=self.scroller.getCanvas(),text=display_text(scenery_name(key)),
                text_align=0,text_scale=14,text_pos=(24,0),text_fg=(.86,.94,.89,1),
                indicatorValue=record.enabled,indicator_scale=12,indicator_pos=(6,0,4),
                frameColor=(0,0,0,0),relief=None,pos=(8,0,-25-i*55),
                command=self.toggle_scenery,extraArgs=[key])
            self.rows.append(check);self.checks[key]=check
        self.note['text']=f'{len(records)} objects · selections are saved per scenery style.'

    def toggle_scenery(self,value,key):
        from copy import deepcopy
        settings=deepcopy(self.app.settings);settings.scenery[key]=bool(value)
        settings.save(self.app.args.settings);self.app.settings=settings
        self.app.scenery_objects.set_enabled(key,value)

    def toggle(self,value,key):
        self.app.decorations.set_enabled(key,value)

    def refresh(self):
        self.app.decorations.refresh()
        self.rebuild()
