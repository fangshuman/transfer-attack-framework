import torch
import torch.nn as nn

from .base import Attack

def get_source_layers(model_name, model):
    model = model.model

    if model_name == "vgg16_bn":  # 0...43
        # exclude relu, maxpool
        return list(
            enumerate(
                map(
                    lambda name: (
                        name,
                        model._modules.get("_features")._modules.get(name),
                    ),
                    [str(v) for v in range(44)],
                )
            )
        )

    elif model_name == "resnet50":  # 0...7
        # exclude relu, maxpool
        return list(
            enumerate(
                map(
                    lambda name: (name, model._modules.get(name)),
                    ["conv1", "bn1", "layer1", "layer2", "layer3", "layer4", "fc"],
                )
            )
        )

    elif model_name == "densenet121":  # 0...9
        # exclude relu, maxpool
        layer_list = list(
            map(
                lambda name: (name, model._modules.get("features")._modules.get(name)),
                [
                    "conv0",
                    "denseblock1",
                    "transition1",
                    "denseblock2",
                    "transition2",
                    "denseblock3",
                    "transition3",
                    "denseblock4",
                    "norm5",
                ],
            )
        )
        layer_list.append(("classifier", model._modules.get("classifier")))
        return list(enumerate(layer_list))

    elif model_name == "inceptionresnetv2":  # 0...17
        # exclude relu, maxpool
        return list(
            enumerate(
                map(
                    lambda name: (name, model._modules.get(name)),
                    [
                        "conv2d_1a",
                        "conv2d_2a",
                        "conv2d_2b",
                        "maxpool_3a",
                        "conv2d_3b",
                        "conv2d_4a",
                        "maxpool_5a",
                        "mixed_5b",
                        "repeat",
                        "mixed_6a",
                        "repeat_1",
                        "mixed_7a",
                        "repeat_2",
                        "block8",
                        "conv2d_7b",
                        "avgpool_1a",
                        "last_linear",
                    ],
                )
            )
        )

    elif model_name == "inceptionv4":  # 0...21
        # exclude relu, maxpool
        layer_list = list(
            map(
                lambda name: (name, model._modules.get("features")._modules.get(name)),
                [str(v) for v in range(22)],
            )
        )
        return list(enumerate(layer_list))

    elif model_name == "inceptionv3":  # 0...10
        # exclude relu, maxpool
        layer_list = list(
            map(
                lambda name: (name, model._modules.get(name)),
                [
                    "Conv2d_1a_3x3",
                    "Conv2d_2a_3x3",
                    "Conv2d_2b_3x3",
                    "Conv2d_3b_1x1",
                    "Conv2d_4a_3x3",
                    "Mixed_5b",
                    "Mixed_5c",
                    "Mixed_5d",
                    "Mixed_6a",
                    "Mixed_6b",
                    "Mixed_6c",
                ],
            )
        )
        return list(enumerate(layer_list))

    else:
        raise NotImplementedError(
            "Current code only supports vgg/resnet/densenet/inceptionv3/inceptionv4/inceptionresnetv2. Please check souce model name."
        )


class ILAProjLoss(nn.Module):
    def __init__(self):
        super(ILAProjLoss, self).__init__()

    def forward(self, old_attack_mid, new_mid, original_mid):
        x = (old_attack_mid - original_mid).view(1, -1)  # y'-y
        y = (new_mid - original_mid).view(1, -1)  # y"-y
        x_norm = x / x.norm()

        proj_loss = torch.mm(y, x_norm.transpose(0, 1)) / x.norm()
        return proj_loss


class ILA_Attacker(Attack):
    config = {
        "eps": 16,
        "nb_iter": 20,
        "step_size_pgd": 0.008 * 255,
        "step_size_ila": 0.01 * 255,
        "gamma": 1.0,  # using sgm when gamma < 1.0
    }

    def __init__(
        self,
        attack_name,
        model,
        loss_fn,
        args,
    ):
        self.model_name = args.source_model
        self.model = model
        self.loss_fn = loss_fn
        self.ila_layer = args.ila_layer
        self.eps = args.eps
        self.nb_iter = args.nb_iter
        self.step_size_pgd = args.step_size_pgd
        self.step_size_ila = args.step_size_ila
        self.target = args.target

    def get_feature_layer(self):
        source_layers = get_source_layers(self.model_name, self.model)
        return source_layers[self.ila_layer][1][1]

    def perturb(self, x, y):
        # pgd attack
        pgd_nb_iter = self.nb_iter // 2
        delta = torch.zeros_like(x)
        delta.requires_grad_()

        for i in range(pgd_nb_iter):
            outputs = self.model(x + delta)
            loss = self.loss_fn(outputs, y)
            if self.target:
                loss = -loss

            loss.backward()

            grad_sign = delta.grad.data.sign()
            delta.data = delta.data + self.step_size_pgd * grad_sign
            delta.data = torch.clamp(delta.data, -self.eps, self.eps)
            delta.data = torch.clamp(x.data + delta, 0.0, 1.0) - x

            delta.grad.data.zero_()

        x_adv = torch.clamp(x + delta, 0.0, 1.0)

        # import ipdb; ipdb.set_trace()

        # ila attack
        ila_nb_iter = self.nb_iter - pgd_nb_iter

        def get_mid_output(m, i, o):
            global mid_output
            mid_output = o

        feature_layer = self.get_feature_layer()
        h = feature_layer.register_forward_hook(get_mid_output)

        out_0 = self.model(x.data)
        mid_output_0 = torch.zeros_like(mid_output)
        mid_output_0.copy_(mid_output)  # F_l(x)

        out_1 = self.model(x_adv.data)
        mid_output_1 = torch.zeros_like(mid_output)
        mid_output_1.copy_(mid_output)  # F_l(x')

        delta_ila = torch.zeros_like(x)
        delta_ila.requires_grad_()

        for i in range(ila_nb_iter):
            out_2 = self.model(x + delta_ila)

            loss = ILAProjLoss()(
                mid_output_1.detach(),
                mid_output,
                mid_output_0.detach(),
            )
            if self.target:
                loss = -loss

            loss.backward()

            grad_sign = delta_ila.grad.data.sign()
            delta_ila.data = delta_ila.data + self.step_size_ila * grad_sign
            delta_ila.data = torch.clamp(delta_ila.data, -self.eps, self.eps)
            delta_ila.data = torch.clamp(x.data + delta_ila, 0.0, 1.0) - x

            delta_ila.grad.data.zero_()

        h.remove()

        x_adv_2 = torch.clamp(x + delta_ila, 0.0, 1.0)

        return x_adv_2
