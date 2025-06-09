__all__ = ('MetaRecord', 'MetaMap', 'MetaList', 'PointGeom', 'metainit',)

import os, sys
import datetime, json
from collections import namedtuple, defaultdict
import math

def metainit():
    MetaRecord.TODAY = datetime.datetime.now().strftime('%Y-%m-%d')

PointGeom = namedtuple('PointGeom', ['xc', 'yc'])
def togeom(o):
    if isinstance(o, PointGeom):
        return o
    if len(o) in (2,3):
        return PointGeom(float(o[0]), float(o[1]))
    raise ValueError('Must be a list or tuple (x,y)')

class MetaRecord(object):
    CURRENT_USER = os.getenv('USERNAME', os.getenv('USER', '=Anonymous='))
    TODAY = None
    COMMENT = None
    REAL_USER = None
    def __init__(self, **kwarg):
        self._id = 1
        if not 'user' in kwarg:
            kwarg['user'] = MetaRecord.CURRENT_USER
        if not 'when' in kwarg:
            kwarg['when'] = MetaRecord.TODAY
        if not 'realUser' in kwarg and MetaRecord.REAL_USER and \
                kwarg['user'] == MetaRecord.CURRENT_USER and kwarg['when'] == MetaRecord.TODAY:
            kwarg['realUser'] = MetaRecord.REAL_USER
        self.__dict__.update(kwarg)
    #
    @classmethod
    def current_key(cls):
        return (cls.TODAY, cls.CURRENT_USER)
    #
    @property
    def metakey(self):
        return (self.when, self.user, self._id)
    @property
    def userkey(self):
        return (self.when, self.user)
    #
    @property
    def who(self):
        if hasattr(self, 'method'):
            return self.method
        return self.user
    #
    @property
    def realWho(self):
        if hasattr(self, 'method'):
            return self.method
        if hasattr(self, 'realUser'):
            return self.realUser
        return self.user
    #
    @realWho.setter
    def realWho(self, v):
        if not v or self.who == v:
            if 'realUser' in self.__dict__:
                del self.__dict__['realUser']
        else:
            self.__dict__['realUser'] = v
    #
    @property
    def description(self):
        parts = []
        o = self.as_jsonable()
        for attr in ('user', 'when', 'method', 'realUser'):
            if attr in o:
                del o[attr]
        if 'comment' in o:
            parts.append(o.pop('comment'))
        for k in sorted(o.keys()):
            v = o[k]
            parts.append(f'{k}={v}')
        return ' '.join(parts)
    #
    def __hash__(self):
        return hash(self.metakey)
    #
    def as_jsonable(self):
        res = {}
        if MetaRecord.COMMENT and self.userkey == self.current_key():
            res['comment'] = MetaRecord.COMMENT
        for k, v in self.__dict__.items():
            if not k.startswith('_') and isinstance(v, (str, int, float, bool)):
                res[k] = v
        return res
    #
    def copy(self):
        return MetaRecord(**self.as_jsonable())
    #
    def __str__(self):
        return f'{self.realWho} - {self.when} {self.description}'
    #

class MetaMap(object):
    def __init__(self, default=None):
        self._next_id = 1
        self._default = default.copy() if default else MetaRecord()
        self._default._id = self._next_id
        self._next_id += 1
        #
        self._metamap = {self._default.metakey : self._default}
        self._omap = {}
        #
        self._oregistry = {}
        self._created = {}
        self._deleted = {}
    #
    @property
    def default(self):
        return self._default
    @default.setter
    def default(self, v):
        if isinstance(v, MetaRecord):
            v = v.metakey
        elif not isinstance(v, tuple):
            return
        if v in self._metamap:
            self._default = self._metamap[v]
    #
    def _last_userkey(self, meta):
        res = None
        for _meta in self._metamap.values():
            if _meta.userkey == meta.userkey:
                if res is None or res._id < _meta._id:
                    res = _meta
        return res
    def addmeta(self, meta, setdefault=False, newid=False):
        if not meta: meta = MetaRecord()
        else: meta = meta.copy()
        comment = meta.comment if hasattr(meta, 'comment') else None
        _meta = None if newid else self._last_userkey(meta)
        if _meta is None:
            meta._id = self._next_id
            self._next_id += 1
            self._metamap[meta.metakey] = meta
        else:
            meta = _meta
        if setdefault:
            if comment and not hasattr(meta, 'comment'):
                meta.__dict__['comment'] = comment
            self._default = meta
        return meta
    #
    def can_delete_meta(self, mkey):
        if isinstance(mkey, MetaRecord):
            mkey = mkey.metakey
        elif not isinstance(mkey, tuple):
            return False
        if not mkey in self._metamap:
            return False
        mrec = self._metamap[mkey]
        if mrec.userkey != MetaRecord.current_key():
            return False
        for _mrec in self._omap.values():
            if _mrec is mrec:
                return False
        for _mrec in self._metamap.values():
            if _mrec.userkey == mrec.userkey and _mrec.metakey != mrec.metakey:
                return True
        return False
    #
    def delmeta(self, mkey):
        if not self.can_delete_meta(mkey):
            return False
        if isinstance(mkey, MetaRecord):
            mkey = mkey.metakey
        mrec = self._metamap.pop(mkey)
        if mrec is self._default:
            self._default = self._last_userkey(mrec)
        return True
    #
    def addobj(self, obj, meta=None):
        oid = id(obj)
        if oid in self._omap and meta is None:
            return
        if meta is None:
            meta = self._default
        self._omap[oid] = meta
        #
        mkey = meta.metakey
        self._oregistry[oid] = obj
        if not oid in self._created:
            self._created[oid] = mkey
    #
    def delobj(self, obj, meta=None):
        if meta is None:
            meta = self._default
        self._deleted[id(obj)] = meta.metakey
    #
    def objmeta(self, obj):
        return self._omap.get(id(obj))
    #
    def itermapping(self, objs):
        mmap = {self.default.metakey : []}
        for obj in objs:
            meta = self._omap.get(id(obj), None)
            if not meta:
                meta = self._default
                self._omap[id(obj)] = meta
            mkey = meta.metakey
            if not mkey in mmap:
                lst = []
                mmap[mkey] = lst
            else:
                lst = mmap[mkey]
            lst.append(obj)
        #
        for mkey, mrec in self._metamap.items():
            if not mkey in mmap and mrec.userkey == MetaRecord.current_key():
                mmap[mkey] = []
        for mkey in sorted(mmap.keys(), reverse=True):
            lst = mmap[mkey]
            yield self._metamap[mkey], lst
    #

class MetaTracker(object):
    class MetaCounter(object):
        __slots__ = ('active', 'created', 'deleted', 'modified')
        def __init__(self):
            self.active = 0
            self.created = 0
            self.deleted = 0
            self.modified = 0
        def is_empty(self):
            return 0 == self.active + self.created + self.deleted + self.modified
    #
    def __init__(self, meta, olist):
        self.meta = meta
        self.olist = olist
        #
        self.idmap = dict([(id(o), o) for o in olist])
        #
        self.galive = {}
        self.gdead = {}
        self.metaset = set()
        self.metaset.add(self.meta.default.metakey)
        for oid, obj in self.meta._oregistry.items():
            og = togeom(obj)
            if oid in self.idmap:
                self.galive[oid] = og
            else:
                self.gdead[oid] = og
            mrec = self.meta._omap.get(oid, self.meta._default)
            self.metaset.add(mrec.metakey)
        #
        self.delomap = defaultdict(set)
        for oid, mkey in self.meta._deleted.items():
            self.delomap[mkey].add(oid)
        #
        self.creomap = defaultdict(set)
        for oid, mkey in self.meta._created.items():
            if mkey in self.delomap:
                deadset = self.delomap[mkey]
                if oid in deadset:
                    deadset.remove(oid)
                    continue
            self.creomap[mkey].add(oid)
    #
    def iteroutput(self):
        metaord = sorted(self.metaset)
        metareg = {}
        metamap = {self.meta.default.metakey : []}
        nextmid = 1
        for mkey in metaord:
            metareg[mkey] = nextmid
            nextmid += 1
            metamap[mkey] = []
        #
        for obj in self.olist:
            oid = id(obj)
            mrec = self.meta._omap.get(oid, None)
            if not mrec:
                mrec = self.meta._default
                self.meta._omap[oid] = mrec
            metamap[mrec.metakey].append(obj)
        #
        for mkey in metaord:
            mrec = self.meta._metamap[mkey]
            mstr = json.dumps(mrec.as_jsonable())
            yield ['#meta', mstr]
            for pt in metamap[mkey]:
                yield([f'{pt[0]:.3f}', f'{pt[1]:.3f}'])
        #
        for delmkey, oids in self.delomap.items():
            if not delmkey in metareg: continue
            delmid = metareg[delmkey]
            for oid in oids:
                if not oid in self.gdead: continue
                og = self.gdead[oid]
                cremkey = self.meta._created[oid]
                yield ['#del', metareg[cremkey], delmid, og.xc, og.yc]
    #
    def finddead(self, og, delset):
        for oid in delset:
            if not oid in self.gdead: continue
            og1 = self.gdead[oid]
            dx = og1.xc - og.xc
            dy = og1.yc - og.yc
            dist = math.sqrt(dx*dx + dy*dy)
            if dist < 1.5:
                return oid
        return None
    #
    def getstats(self):
        replaces = set()
        replacedby = set()
        for mkey, creset in self.creomap.items():
            delset = self.delomap[mkey]
            for oid in creset:
                if oid in self.galive:
                    og = self.galive[oid]
                else:
                    og = self.gdead[oid]
                poid = self.finddead(og, delset)
                if not poid is None:
                    replaces.add(oid)
                    replacedby.add(poid)
        #
        stats = defaultdict(MetaTracker.MetaCounter)
        for oid in self.idmap.keys():
            mrec = self.meta._omap.get(oid, self.meta._default)
            stats[mrec.metakey].active += 1
        #
        for mkey, creset in self.creomap.items():
            cntr = stats[mkey]
            for oid in creset:
                if oid in replaces:
                    cntr.modified += 1
                else:
                    cntr.created += 1
        #
        for mkey, delset in self.delomap.items():
            cntr = stats[mkey]
            for oid in delset:
                if oid in self.idmap or oid in replacedby:
                    continue
                cntr.deleted += 1
        res = []
        for mkey in sorted(stats.keys()):
            mrec = self.meta._metamap[mkey]
            res.append((mrec, stats[mkey]))
        return res
    #
            

class MetaList(object):
    FWD_LIST_ATTR = ['clear', 'copy', 'count', 'index', 'pop', 'remove', 'reverse', 'sort']
    def __init__(self, *arg, **kwarg):
        if 'meta' in kwarg:
            self._meta = kwarg.pop('meta')
        else:
            self._meta = MetaMap()
        self._lst = list(*arg, **kwarg)
        for obj in self._lst:
            self._meta.addobj(obj)
        #
        self._gray = set()
    #
    @property
    def meta(self):
        return self._meta
    #
    def objmeta(self, item):
        return self._meta.objmeta(item)
    #
    def setGrayMeta(self, metalist):
        self._gray.clear()
        for mrec in metalist:
            if isinstance(mrec, MetaRecord):
                mrec = mrec.metakey
            self._gray.add(mrec)
    #
    def isGrayMetaRec(self, mrec):
        if isinstance(mrec, MetaRecord):
            mrec = mrec.metakey
        return mrec in self._gray
    #
    def isGray(self, item):
        mr = self.objmeta(item)
        return mr.metakey in self._gray
    #
    def __getattribute__(self, item):
        if item in MetaList.FWD_LIST_ATTR:
            return self._lst.__getattribute__(item)
        return super(MetaList, self).__getattribute__(item)
    #
    def _idmap(self):
        return dict([(id(o), o) for o in self._lst])
    def _finddeleted(self, idmap):
        for o in self._lst:
            oid = id(o)
            if oid in idmap:
                del idmap[oid]
        return idmap.values()
    def _markdeleted(self, idmap):
        for o in self._finddeleted(idmap):
            self._meta.delobj(o)
    #
    def append(self, x):
        self._lst.append(x)
        self._meta.addobj(x)
    #
    def extend(self, iterable):
        for x in iterable:
            self._lst.append(x)
            self._meta.addobj(x)
    #
    def update(self, iterable):
        idmap = self._idmap()
        self._lst.clear()
        self.extend(iterable)
        self._markdeleted(idmap)
    #
    def insert(self, i, x):
        self._lst.insert(i, x)
        self._meta.addobj(x)
    #
    def itermapping(self):
        return self._meta.itermapping(self._lst)
    #
    def canDeleteMetaRec(self, mrec):
        return self._meta.can_delete_meta(mrec)
    #
    def deleteMetaRec(self, mrec):
        return self._meta.delmeta(mrec)
    #
    def __str__(self):
        return self._lst.__str__()
    def __repr__(self):
        return self._lst.__repr__()
    def __len__(self):
        return self._lst.__len__()
    def __getitem__(self, key):
        return self._lst.__getitem__(key)
    def __setitem__(self, key, value):
        idmap = self._idmap()
        self._lst.__setitem__(key, value)
        self._meta.addobj(value)
        self._markdeleted(idmap)
    def __delitem__(self, key):
        idmap = self._idmap()
        rc = self._lst.__delitem__(key)
        self._markdeleted(idmap)
        return rc
    def __iter__(self):
        return self._lst.__iter__()
    def __reversed__(self):
        return self._lst.__reversed__()
    def __contains__(self, item):
        return self._lst.__contains__(item)
    #
    def gettracker(self):
        return MetaTracker(self._meta, self._lst)
    def iteroutput(self):
        tracker = self.gettracker()
        return tracker.iteroutput()
    #

metainit()
