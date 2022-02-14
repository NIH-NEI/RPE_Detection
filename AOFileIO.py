import os
import csv
import SimpleITK as sitk
import math
import numpy as np

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
        #return sitk.GetArrayFromImage(itk_img), itk_img.GetSpacing(), itk_img.GetOrigin()
        return itk_img

    def read_annotations(self, file_name, ignore_errors=True):
        #file_name = file_name.replace(' ', '')
        res_pts = []
        try:
            with open(file_name) as csv_file:
                csv_reader = csv.reader(csv_file, delimiter=',')
                for row in csv_reader:
                    if len(row) == 1 and len(row[0]) == 0: continue
                    if row[0].startswith('#'): continue
                    tmp_pt = []
                    for id, item in enumerate(row):
                        tmp_pt.append(float(item))
                    # Add small negative value (-0.001) to Z-coordinate to make
                    # annotation closer to the camera
                    tmp_pt.append(-0.001)
                    res_pts.append(tmp_pt)
        except Exception:
            if ignore_errors:
                return []
            raise
        return res_pts

    def write_points(self, file_name, pts, img_origin, img_spacing):
        #file_name = file_name.replace(' ', '')
        with open(file_name, mode='w', newline='') as annotation_file:
            annotation_writer = csv.writer(annotation_file, delimiter=',')
            for pt in pts:
                annotation_writer.writerow([(pt[0]-img_origin[0])/img_spacing[0],
                                            (pt[1]-img_origin[1])/img_spacing[1]])

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

        res_pts = []
        for pt in pts:
            for i in range(img_dim):
                pt[i] = pt[i]*img_spacing[i] + img_origin[i]

            res_pts.append(pt)

        return res_pts

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

    def write_annotations(self, dir_name, input_data):
        for (img_name, img, pts) in zip(input_data['RPE image names'], input_data['RPE images'],
                                        input_data['RPE annotations']):
            img_path = os.path.join(dir_name, img_name)
            pt_name = img_path + '.csv'
            self.write_points(pt_name, pts, img.GetOrigin(), img.GetSpacing())



