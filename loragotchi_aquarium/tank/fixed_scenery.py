"""Fixed hosted scenery: share authored meshes and their exact solid owners.

No desktop masks, relocation or layout configuration in the managed viewer.
"""
from dataclasses import dataclass
from panda3d.core import NodePath


@dataclass
class FixedObject:
    node: object
    position: tuple
    shapes: tuple
    batched: bool
    enabled: bool
    bubble_origins: tuple = ()


class FixedScenery:
    def __init__(self, app):
        self.app=app;self.records={};self.batch=None
        self.sources=NodePath('hosted-scenery-sources')

    def clear(self):
        for key,record in self.records.items():
            self.app.sim.physics.replace_shapes(key,[])
            record.node.removeNode()
        self.records.clear()
        if self.batch is not None:self.batch.removeNode()
        self.batch=None

    def register(self,key,node,shapes=(),*,batched=False,enabled=True,sway=False):
        position=tuple(node.getPos(self.app.scene))
        enabled=self.app.settings.scenery.get(key,enabled)
        self.records[key]=FixedObject(node,position,tuple(shapes),batched,enabled)
        if node.hasPythonTag('bubble-origins'):
            self.records[key].bubble_origins=tuple(node.getPythonTag('bubble-origins'))
            node.clearPythonTag('bubble-origins')
        if batched:node.wrtReparentTo(self.sources)
        self._apply(key)

    def _apply(self,key):
        record=self.records[key]
        record.node.show() if record.enabled else record.node.hide()
        self.app.sim.physics.replace_shapes(key,[(shape,tuple(record.position[i]+offset[i] for i in range(3)),hpr)
            for shape,offset,hpr in record.shapes] if record.enabled else [])

    def finish(self,parent):
        self.batch=parent.attachNewNode('hosted-static-scenery')
        self._batch()
        self.app.sim.obstacles_changed()

    def _batch(self):
        self.batch.getChildren().detach()
        for record in self.records.values():
            if record.batched and record.enabled:record.node.copyTo(self.batch)
        self.batch.flattenStrong()

    def set_enabled(self,key,value):
        self.records[key].enabled=bool(value);self._apply(key);self._batch()
        self.app.sim.obstacles_changed()
