import os
import csv
import json
from collections import defaultdict
import SimpleITK as sitk
import math
import numpy as np
from AOMetaList import *

def write_points(file_name, pts, img_origin, img_spacing):
    with open(file_name, mode='w', newline='') as annotation_file:
        annotation_writer = csv.writer(annotation_file, delimiter=',')
        for pt in pts:
            annotation_writer.writerow([(pt[0] - img_origin[0]) / img_spacing[0],
                                        (pt[1] - img_origin[1]) / img_spacing[1]])

class ao_fileIO():
    def __init__(self):
        pass

    def read_image(self, img_name):
        itk_img = sitk.ReadImage(img_name)
        ndim = len(itk_img.GetSize())
        itk_img.SetOrigin([0]*ndim)
        itk_img.SetSpacing([1]*ndim)
        #return sitk.GetArrayFromImage(itk_img), itk_img.GetSpacing(), itk_img.GetOrigin()
        return itk_img

    def read_annotations(self, file_name, ignore_errors=True):
        #file_name = file_name.replace(' ', '')
        res_pts = defaultdict(list)
        unchecked = None
        try:
            with open(file_name) as csv_file:
                csv_reader = csv.reader(csv_file, delimiter=',')
                cframe = 0
                nextmetaid = 1
                metareg = {}
                for row in csv_reader:
                    if len(row) == 1 and len(row[0]) == 0: continue
                    if row[0] == '#frame':
                        cframe = int(row[1])
                        nextmetaid = 1
                        metareg = {}
                        continue
                    if row[0] == '#unchecked':
                        unchecked = [int(v) for v in row[1:]]
                        continue
                    
                    is_meta = is_del = False
                    if row[0].startswith('#'):
                        if row[0] == '#meta':
                            is_meta = True
                        elif row[0] == '#del':
                            is_del = True
                        else:
                            continue
                        
                    if not cframe in res_pts:
                        res_pts[cframe] = MetaList(meta=MetaMap(MetaRecord(user='=Diskfile=')))
                    pts = res_pts[cframe]
                    if is_meta:
                        try:
                            kwarg = json.loads(row[1])
                            mrec = pts.meta.addmeta(MetaRecord(**kwarg), setdefault=True, newid=True)
                            metareg[nextmetaid] = mrec
                            nextmetaid += 1
                        except Exception as ex:
                            print(ex)
                        continue
                    if is_del:
                        try:
                            cremeta = metareg[int(row[1])]
                            delmeta = metareg[int(row[2])]
                            obj = PointGeom(float(row[3]), float(row[4]))
                            pts.meta.addobj(obj, cremeta)
                            pts.meta.delobj(obj, delmeta)
                        except Exception as ex:
                            print(ex)
                        continue
                        
                    pts.append([float(row[0]), float(row[1]), -0.001])
                #
        except Exception as ex:
            if ignore_errors:
                return {}
            raise
        for pts in res_pts.values():
            pts.meta.addmeta(MetaRecord(), setdefault=True)
        if unchecked:
            res_pts['unchecked'] = unchecked
        return res_pts

    def write_points(self, file_name, all_pts, img_origin, img_spacing):
        #file_name = file_name.replace(' ', '')
        with open(file_name, mode='w', newline='') as annotation_file:
            annotation_writer = csv.writer(annotation_file, delimiter=',')
            if isinstance(all_pts, (list, tuple)):
                all_pts = {0:all_pts}
            unchecked = None
            if 'unchecked' in all_pts:
                unchecked = all_pts.pop('unchecked')
            for fr in sorted(all_pts.keys()):
                pts = all_pts[fr]
                annotation_writer.writerow(['#frame', fr])
                if hasattr(pts, 'iteroutput'):
                    for row in pts.iteroutput():
                        annotation_writer.writerow(row)
                else:
                    for pt in pts:
                        annotation_writer.writerow(
                            [(pt[0]-img_origin[0])/img_spacing[0], (pt[1]-img_origin[1])/img_spacing[1]]
                        )
            if unchecked:
                annotation_writer.writerow(['#unchecked']+unchecked)
    #
    def write_annotation_stats(self, dir_name, input_data, suffix='_stats.csv'):
        cnt = 0
        for imdat in input_data:
            fn = imdat.name + suffix
            combo = {}
            for pts in imdat.all_annotations:
                if not hasattr(pts, 'gettracker'): continue
                tracker = pts.gettracker()
                for mrec, stat in tracker.getstats():
                    if stat.is_empty(): continue
                    mkey = mrec.metakey
                    if mkey in combo:
                        row = combo[mkey]
                        row[0] += stat.active
                        row[1] += stat.created
                        row[2] += stat.deleted
                        row[3] += stat.modified
                    else:
                        combo[mkey] = [stat.active, stat.created, stat.deleted, stat.modified,
                            mrec.when, mrec.who, mrec.realWho, mrec.description]
            if len(combo) == 0: continue
            stats_file_path = os.path.join(dir_name, fn)
            with open(stats_file_path, 'w', newline='', encoding='utf-8') as stats_file:
                wr = csv.writer(stats_file, delimiter=',')
                wr.writerow(['ID', 'Date', 'Origin', 'User',
                            'Active', 'Created', 'Deleted', 'Modified', 'Comment'])
                nextid = 1
                for mkey in sorted(combo.keys()):
                    active, created, deleted, modified, when, who, realWho, description = combo[mkey]
                    wr.writerow([nextid, when, who, realWho, active, created, deleted, modified, description])
                    nextid += 1
            cnt += 1
        return cnt
    
    #check if points in image coocrdinate or physical coordinate
    def is_annotation_spaced(self, pts, img):
        if len(pts) == 0:
            return False

        # if points in image coordinate, then the decimal of points should be close to zero or 0.999
        n_pts = np.asarray(pts)
        max_vals = np.amax(n_pts, axis=0)
        img_origin = img.GetOrigin()
        img_spacing = img.GetSpacing()
        img_size = img.GetSize()

        if max_vals[0]<=(img_origin[0]+img_size[0]*img_spacing[0]) and max_vals[1]<=(img_origin[1]+img_size[1]*img_spacing[1]):
            return False
        else:
            return True

    def scale_annotations(self, pts, img):
        img_origin = img.GetOrigin()
        img_spacing = img.GetSpacing()
        img_dim = img.GetDimension()

        for pt in pts:
            for i in range(img_dim):
                pt[i] = pt[i]*img_spacing[i] + img_origin[i]

        return pts

    def create_training_image(self, itk_img, pts):
        res_img = sitk.Image(itk_img.GetSize(), sitk.sitkUInt8)
        res_img.SetSpacing(itk_img.GetSpacing())
        res_img.CopyInformation(itk_img)
        #res_img[::] = 0
        for pt in pts:
            xid = (int)((pt[0]-itk_img.GetOrigin()[0])/itk_img.GetSpacing()[0]+0.5)
            yid = (int)((pt[1] - itk_img.GetOrigin()[1]) / itk_img.GetSpacing()[1]+0.5)
            if xid >= 0 and xid < itk_img.GetSize()[0] and yid >= 0 and yid < itk_img.GetSize()[1]:
                res_img.SetPixel(xid, yid, 255)

        res_img = sitk.BinaryDilate(res_img, 3, sitk.sitkBall, 0, 255)
        return res_img

    # def write_annotations(self, apath, all_pts, origin, spacing):
    #     for (img_name, img, pts) in zip(input_data['image names'], input_data['images'],
    #                                     input_data['annotations']):
    #         img_path = os.path.join(dir_name, img_name)
    #         pt_name = img_path + '.csv'
    #         if (len(pts) == 0 and not os.isfile(pt_name)): continue
    #         self.write_points(pt_name, pts, img.GetOrigin(), img.GetSpacing())


if __name__ == '__main__':
    
    img_name = r'C:\MSC\SampleImages\sample_stack.tif'
    itk_img = sitk.ReadImage(img_name)
    print(dir(itk_img))
    print(itk_img.GetSize())
    
