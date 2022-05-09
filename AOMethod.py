from skimage.transform import resize
import keras
from keras.models import Model
from keras.layers import Input, add, concatenate, Conv2D, MaxPooling2D, Conv2DTranspose, BatchNormalization, Dropout
from keras.layers.advanced_activations import LeakyReLU
from keras import backend as K
import tensorflow as tf
from skimage.transform import resize
import os
import numpy as np
import SimpleITK as sitk
import numbers
# import matplotlib.pyplot as plt
import scipy.cluster.hierarchy as hcluster
from pathlib import Path

try:
    import sys
    MODEL_WEIGHTS_BASE = sys._MEIPASS
except AttributeError:
    MODEL_WEIGHTS_BASE = None

from segmentation_models import Linknet
from segmentation_models.backbones import backbones as smbb

import multiprocessing as mp
core_num = mp.cpu_count()
config = tf.ConfigProto(
    inter_op_parallelism_threads=core_num,
    intra_op_parallelism_threads=core_num)
config.gpu_options.allow_growth = True
sess = tf.Session(config=config)

training_img_rows = 256
training_img_cols = 256
training_img_mean = 94.25525665283203
training_img_std = 39.701194763183594
scanning_img_rows = 317
scanning_img_cols = 317

# def display_images(*images):
#     num_of_imgs = len(images)
#     f, axarr = plt.subplots(1, num_of_imgs)
#     for i in range(num_of_imgs):
#         axarr[0][i].imshow(images[i], cmap='gray')
#     plt.show()

def display_images(image):
    plt.imshow(image, cmap='gray')
    plt.show()


class ao_method():
    def __init__(self):
        self._rpe_detection_model = None

    def create_linknet_model(self, backbone, training_size, output_class):
        if isinstance(training_size, numbers.Number):
            training_size = (int(training_size), int(training_size))

        model = Linknet(backbone_name=backbone, input_shape=(training_size[0], training_size[1], 1),
                        upsample_layer='transpose', classes=output_class)
        model.summary()
        return model

    def create_detection_models(self, model_weight_dir):
        # extract a list of model weights to create detection models
        if MODEL_WEIGHTS_BASE is None:
            # Devel or --onedir
            _model_weight_dir = model_weight_dir
            skip = 0
        else:
            # --onefile : special case for single exe : handle model_weight_dir not relative to current dir
            _model_weight_dir = os.path.join(MODEL_WEIGHTS_BASE, model_weight_dir)
            skip = len(Path(MODEL_WEIGHTS_BASE).parts)
        
        model_files = os.listdir(_model_weight_dir)
        model_dictionary = {}
        if len(model_files) == 0:
            return model_dictionary #return an empty dictionary, no detection model available

        for dirpath, dirnames, filenames in os.walk(_model_weight_dir):
            for filename in [f for f in filenames if f.endswith(".h5")]:
                p = Path(os.path.join(dirpath, filename))
                p_parts = list(p.parts[skip:])
                if len(p_parts) == 2:
                    model_key, extension = os.path.splitext(p.parts[-1])
                    model_val = os.path.join(dirpath, filename)
                    model_dictionary[model_key] = model_val
                elif len(p_parts) >= 2:
                    model_key, extension = os.path.splitext(p.parts[-1])
                    model_key = '-'.join(p_parts[1:-1]+[model_key])
#                     model_sub_dir = ''
#                     for i in range(1, len(p_parts)-1):
#                         model_sub_dir = model_sub_dir + p_parts[i] + '-'
#                     model_key = model_sub_dir + model_key
                    model_val = os.path.join(dirpath, filename)
                    model_dictionary[model_key] = model_val

        return model_dictionary

    def create_detection_model(self, model_name, model_weight_path):
        if not os.path.isfile(model_weight_path):
            raise ValueError('could not load weight {}'.format(model_weight_path))

        parts = model_name.split('_')
        application = parts[0]
        backbone = 'densenet121'
        outclass = 1
        for pt in parts:
            if pt == 'voronoi':
                outclass = 2
            elif pt in smbb.backbones:
                backbone = pt

        self._rpe_detection_model = self.create_linknet_model(backbone=backbone,
            training_size=(training_img_rows, training_img_cols),
            output_class=outclass)
        self._rpe_detection_model.load_weights(model_weight_path)


    def preprocess_images(self, img):
        input_img_size = img.GetSize()
        img_arr = sitk.GetArrayFromImage(img)

        normalized_imgs = None
        if input_img_size[1] > scanning_img_rows and input_img_size[0] > scanning_img_cols:
            row_subdivision = input_img_size[1] // scanning_img_rows
            col_subdivision = input_img_size[0] // scanning_img_cols
            if input_img_size[1] % scanning_img_rows == 0:
                row_num = row_subdivision
            else:
                row_num = row_subdivision + 1

            if input_img_size[0] % scanning_img_cols == 0:
                col_num = col_subdivision
            else:
                col_num = col_subdivision + 1
            num_of_sub_imgs = row_num * col_num
            normalized_imgs = np.zeros((num_of_sub_imgs, training_img_rows, training_img_cols), dtype=np.float32)

            row_indices = np.zeros((2,), dtype=np.int32)
            col_indices = np.zeros((2,), dtype=np.int32)
            for i in range(row_num):
                if i == row_num - 1 and i * scanning_img_rows < input_img_size[1]:
                    row_indices[0] = input_img_size[1] - scanning_img_rows
                    row_indices[1] = input_img_size[1]
                else:
                    row_indices[0] = i * scanning_img_rows
                    row_indices[1] = (i + 1) * scanning_img_rows

                for j in range(col_num):
                    if j == col_num - 1 and j * training_img_cols < input_img_size[0]:
                        col_indices[0] = input_img_size[0] - scanning_img_cols
                        col_indices[1] = input_img_size[0]
                    else:
                        col_indices[0] = j * scanning_img_cols
                        col_indices[1] = (j + 1) * scanning_img_cols

                    sub_img = img_arr[row_indices[0]:row_indices[1], col_indices[0]:col_indices[1]]
                    sub_img = resize(sub_img, (training_img_rows, training_img_cols), preserve_range=True)
                    # sub_img = sub_img[np.newaxis, ..., np.newaxis]
                    sub_img = sub_img.astype('float32')
                    sub_img -= training_img_mean
                    sub_img /= training_img_std

                    normalized_imgs[j+i*col_num] = sub_img
        else:
            normalized_imgs = np.zeros((1, training_img_rows, training_img_cols), dtype=np.float32)
            sub_img = resize(img_arr, (training_img_rows, training_img_cols), preserve_range=True)
            sub_img = sub_img.astype('float32')
            sub_img -= training_img_mean
            sub_img /= training_img_std
            normalized_imgs[0] = sub_img

        normalized_imgs = normalized_imgs[..., np.newaxis]
        return normalized_imgs

    def compute_probablity_map(self, img, normalized_imgs):
        input_img_size = img.GetSize()

        res_imgs = self._rpe_detection_model.predict(normalized_imgs, verbose=1)

        if res_imgs.shape[-1] == 1:
            res_imgs = np.squeeze(res_imgs, axis=-1)
        else:
            res_imgs = res_imgs[...,0]

        if res_imgs.shape[0] == 1:
            res_imgs = np.squeeze(res_imgs, axis=0)
            prob_img = resize(res_imgs, (input_img_size[1], input_img_size[0]), preserve_range=True)
        else:
            prob_img = np.zeros((input_img_size[1], input_img_size[0]), dtype=np.float32)
            row_subdivision = input_img_size[1] // scanning_img_rows
            col_subdivision = input_img_size[0] // scanning_img_cols

            if input_img_size[1] % scanning_img_rows == 0:
                row_num = row_subdivision
            else:
                row_num = row_subdivision + 1

            if input_img_size[0] % scanning_img_cols == 0:
                col_num = col_subdivision
            else:
                col_num = col_subdivision + 1
            num_of_sub_imgs = row_num * col_num

            row_indices = np.zeros((2,), dtype=np.int32)
            col_indices = np.zeros((2,), dtype=np.int32)
            for i in range(row_num):
                if i == row_num - 1 and i * scanning_img_rows < input_img_size[1]:
                    row_indices[0] = input_img_size[1] - scanning_img_rows
                    row_indices[1] = input_img_size[1]
                else:
                    row_indices[0] = i * scanning_img_rows
                    row_indices[1] = (i + 1) * scanning_img_rows

                for j in range(col_num):
                    if j == col_num - 1 and j * training_img_cols < input_img_size[0]:
                        col_indices[0] = input_img_size[0] - scanning_img_cols
                        col_indices[1] = input_img_size[0]
                    else:
                        col_indices[0] = j * scanning_img_cols
                        col_indices[1] = (j + 1) * scanning_img_cols

                    sub_res_img = res_imgs[j+i*col_num]
                    sub_res_img = resize(sub_res_img, (scanning_img_rows, scanning_img_cols), preserve_range=True)
                    prob_img[row_indices[0]:row_indices[1], col_indices[0]:col_indices[1]] = sub_res_img

        return prob_img

    def postprocess_probability_map(self, img_origin, fov_ratio, prob_img, prob_value, distance_value):
        res_img = np.zeros(prob_img.shape, dtype=np.uint8)
        res_img[prob_img > prob_value] = 1

        dist_img = sitk.SignedMaurerDistanceMap(sitk.GetImageFromArray(res_img), insideIsPositive=True,
                                                squaredDistance=False, useImageSpacing=False)

        dist_s_img = sitk.SmoothingRecursiveGaussian(dist_img, 1.0, True)
        # sitk.WriteImage(dist_s_img, 'dist_img1.hdr')
        dist_s_arr = sitk.GetArrayFromImage(dist_s_img)
        dist_s_arr[dist_s_arr < 0] = 0
        dist_s_img = sitk.GetImageFromArray(dist_s_arr)
        # sitk.WriteImage(dist_s_img, 'dist_img2.hdr')

        peak_filter = sitk.RegionalMaximaImageFilter()
        peak_filter.SetForegroundValue(1)
        peak_filter.FullyConnectedOn()
        peaks = peak_filter.Execute(dist_s_img)
        # sitk.WriteImage(peaks, 'peaks.hdr')

        stats = sitk.LabelShapeStatisticsImageFilter()
        stats.Execute(sitk.ConnectedComponent(peaks))
        detection_centriods = [stats.GetCentroid(l) for l in stats.GetLabels()]

        # clustering
        detection_res = []

        if len(detection_centriods) > 10:
            clusters = hcluster.fclusterdata(detection_centriods, distance_value, criterion="distance")
            min_label = np.amin(clusters)
            max_label = np.amax(clusters)
            np_detection_centroids = np.asarray(detection_centriods)
            for i in range(min_label, max_label + 1, 1):
                pts = np_detection_centroids[np.where(clusters == i)]
                xpos = 0
                ypos = 0

                for pt in pts:
                    xpos += pt[0]
                    ypos += pt[1]
                xpos /= len(pts)
                ypos /= len(pts)

                xpos = img_origin[0] + (xpos - img_origin[0]) / fov_ratio
                ypos = img_origin[1] + (ypos - img_origin[1]) / fov_ratio
                pt = (xpos, ypos)
                detection_res.append(pt)
        return detection_res

    def detect_RPEs(self, img, fov, prob_value, distance_value):
        if self._rpe_detection_model is None:
            return None

        # training fov is 0.75, we need to compute fov ratio difference first
        fov_ratio = fov / 0.75

        # reample image
        euler2d = sitk.Euler2DTransform()
        # Why do we set the center?
        euler2d.SetCenter(img.TransformContinuousIndexToPhysicalPoint(np.array(img.GetSize()) / 2.0))
        euler2d.SetTranslation((0, 0))
        output_spacing = (img.GetSpacing()[0] / fov_ratio, img.GetSpacing()[1] / fov_ratio)
        output_origin = img.GetOrigin()
        output_direction = img.GetDirection()
        output_size = [int(img.GetSize()[0] * fov_ratio + 0.5),
                       int(img.GetSize()[1] * fov_ratio + 0.5)]
        img = sitk.Resample(img, output_size, euler2d, sitk.sitkLinear, output_origin,
                            output_spacing, output_direction)

        normalized_imgs = self.preprocess_images(img)
        prob_img = self.compute_probablity_map(img, normalized_imgs)
        detection_res = self.postprocess_probability_map(output_origin, fov_ratio, prob_img,
                                                         prob_value, distance_value)

        return detection_res


