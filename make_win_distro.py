# Build non-frozen Python win64 distro
import os, sys
import zipfile

APP_VERSION = '1.2.1'

PREFIX = os.path.abspath(os.path.dirname(__file__))
EXCLUDE_DIRS = ('__pycache__', 'build', 'dist',  'dist0', )
EXCLUDE_EXTS = ('.bak', '.bat')
INCLUDE_FILES = ('RPE_Detection.bat',)
ZIP_PREFIX = 'RPE_Detection/'

def proc_dir(cdir):
    print('Scanning:', cdir)
    for fn in os.listdir(cdir):
        fpath = os.path.join(cdir, fn)
        if os.path.isdir(fpath):
            if fn in EXCLUDE_DIRS: continue
            for res in proc_dir(fpath):
                yield res
        else:
            yield fpath

if __name__ == '__main__':
    
    zipfn = 'RPE_Detection-%s-Win64src.zip' % (APP_VERSION,)
    zipdir = os.path.join(PREFIX, 'dist')
    if not os.path.isdir(zipdir):
        os.makedir(zipdir)
    zippath = os.path.join(zipdir, zipfn)
    print('Write:', zippath)
    
    with zipfile.ZipFile(zippath, mode='w', compression=zipfile.ZIP_LZMA) as zip:
        for fpath in proc_dir(PREFIX):
            fdir, fn = os.path.split(fpath)
            if not fn in INCLUDE_FILES:
                _, ext = os.path.splitext(fn)
                ext = ext.lower()
                if ext in EXCLUDE_EXTS: continue
            rpath = ZIP_PREFIX+os.path.relpath(fpath, PREFIX).replace('\\', '/')
            print(rpath)
            zip.write(fpath, rpath)

        pyprefix = os.path.dirname(sys.executable)
        pyzipprefix = ZIP_PREFIX + 'python312/'
        for fpath in proc_dir(pyprefix):
            rpath = pyzipprefix+os.path.relpath(fpath, pyprefix).replace('\\', '/')
            print(rpath)
            zip.write(fpath, rpath)
    
    
    sys.exit(0)
