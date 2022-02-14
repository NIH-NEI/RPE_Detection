
from keras.applications import DenseNet121, DenseNet169, DenseNet201
from keras.applications import VGG16
from keras.applications import VGG19


backbones = {
    "vgg16": VGG16,
    "vgg19": VGG19,
    "densenet121": DenseNet121,
    "densenet169": DenseNet169,
    "densenet201": DenseNet201,

}

def get_backbone(name, *args, **kwargs):
    return backbones[name](*args, **kwargs)