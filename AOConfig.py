import os, datetime, time, shutil

main_wnd = None

class InputList(object):
    def __init__(self, in_list):
        self.in_list = in_list
        #
        self.out_list = []
        for item in in_list:
            if os.path.isfile(item):
                self.out_list.append(item)
            elif os.path.isdir(item):
                for fn in os.listdir(item):
                    fpath = os.path.join(item, fn)
                    if os.path.isfile(fpath):
                        self.out_list.append(fpath)
        self.out_list.sort()
    #
    def get_files(self, suff):
        res = []
        if isinstance(suff, (list, tuple)):
            suff_list = suff
            for fn in self.out_list:
                for suff in suff_list:
                    if fn.lower().endswith(suff):
                        res.append(fn)
                    break
        else:
            for fn in self.out_list:
                if fn.lower().endswith(suff):
                    res.append(fn)
        return res
    #

class HistoryManager(object):
    def __init__(self, state_dir, suffix='.csv', retention_days=365):
        self.state_dir = state_dir
        self.suffix = suffix
        self.retention_days = retention_days
        #
        self.retention = self.retention_days * 24*60*60     # Retention in sec
        self.history_dir = os.path.join(self.state_dir, 'history')
        if not os.path.exists(self.history_dir):
            os.mkdir(self.history_dir)
        else:
            self.delete_expired_history()
    #
    def delete_expired_history(self):
        too_old_ts = time.time() - self.retention
        try:
            for fn in os.listdir(self.history_dir):
                fpath = os.path.join(self.history_dir, fn)
                if os.stat(fpath).st_mtime >= too_old_ts:
                    continue
                if os.path.isdir(fpath):
                    shutil.rmtree(fpath, True)
                else:
                    os.remove(fpath)
        except Exception:
            pass
    #
    def get_local_file(self, img_path):
        basep, _ = os.path.splitext(img_path)
        return basep+self.suffix
    #
    def get_list_name(self, img_path):
        bn, _ = os.path.splitext(os.path.basename(img_path))
        if os.path.isfile(self.get_local_file(img_path)):
            return u'\u221A'+bn
        return u' '+bn
    #
    def get_history_file(self, img_path, compat=True):
        try:
            _ts = datetime.datetime.fromtimestamp(os.stat(img_path).st_mtime_ns * 0.000000001)
            ts = _ts.strftime('%Y%m%d%H%M%S%f')[:-3]
            bn, _ = os.path.splitext(os.path.basename(img_path))
            fn = bn+'.'+ts+self.suffix
            hpath = os.path.join(self.history_dir, fn)
        except Exception:
            return None
        if not os.path.isfile(hpath) and compat:
            try:
                opath = os.path.join(self.history_dir, bn+self.suffix)
                if os.path.isfile(opath):
                    os.rename(opath, hpath)
            except Exception:
                pass
        return hpath
    #