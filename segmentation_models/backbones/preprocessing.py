"""
Image pre-processing functions.
Images are assumed to be read in uint8 format (range 0-255).
"""

from tensorflow.keras.applications import (
    vgg16,
    vgg19,
    densenet,
    inception_v3,
    inception_resnet_v2,
)

identical = lambda x: x

models_preprocessing = {
    'vgg16': vgg16.preprocess_input,
    'vgg19': vgg19.preprocess_input,
    'resnet18': identical,
    'resnet34': identical,
    'resnet50': identical,
    'resnet101': identical,
    'resnet152': identical,
    'resnext50': identical,
    'resnext101': identical,
    'densenet121': densenet.preprocess_input,
    'densenet169': densenet.preprocess_input,
    'densenet201': densenet.preprocess_input,
    'inceptionv3': inception_v3.preprocess_input,
    'inceptionresnetv2': inception_resnet_v2.preprocess_input,
}


def get_preprocessing(backbone):
    return models_preprocessing[backbone]