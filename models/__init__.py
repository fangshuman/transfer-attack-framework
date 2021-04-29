import torch
import torch.nn as nn

# from .torchvision_models import *
# from .inceptionv4 import inceptionv4
# from .inceptionresnetv2 import inceptionresnetv2
import pretrainedmodels

class Wrap(nn.Module):
    def __init__(self, model):
        super(Wrap, self).__init__()
        self.model = model
        self.mean = self.model.mean
        self.std = self.model.std
        self.input_size = self.model.input_size

        self._mean = torch.tensor(self.mean).view(3,1,1).cuda()
        self._std = torch.tensor(self.std).view(3,1,1).cuda()

    def forward(self, x):
        return self.model.forward((x - self._mean) / self._std)


def make_model(arch):
    # if arch == 'vgg16_bn':
    #     model = vgg16_bn(num_classes=1000, pretrained='imagenet')
    # elif arch == 'resnet50':
    #     model = resnet50(num_classes=1000, pretrained='imagenet')
    # elif arch == 'resnet101':
    #     model = resnet101(num_classes=1000, pretrained='imagenet')
    # elif arch == 'resnet152':
    #     model = resnet152(num_classes=1000, pretrained='imagenet')
    # elif arch == 'densenet121':
    #     model = densenet121(num_classes=1000, pretrained='imagenet')
    # elif arch == 'densenet169':
    #     model = densenet169(num_classes=1000, pretrained='imagenet')
    # elif arch == 'densenet201':
    #     model = densenet201(num_classes=1000, pretrained='imagenet')
    # elif arch == 'inceptionv3':
    #     model = inceptionv3(num_classes=1000, pretrained='imagenet')
    # elif arch == 'inceptionv4':
    #     model = inceptionv4(num_classes=1000, pretrained='imagenet')
    # elif arch == 'inceptionresnetv2':
    #     model = inceptionresnetv2(num_classes=1000, pretrained='imagenet')
    # elif arch == 'resnet152':
    #     model = resnet152(num_classes=1000, pretrained='imagenet')
    # else:
    #     raise NotImplementedError(f"No such model: {arch}")     
                      
    model = pretrainedmodels.__dict__[arch](num_classes=1000, pretrained='imagenet')
    return Wrap(model)

