"""
file    : models.py
desc    : contains models implementations
classes : - MLP
          - CNNMnist
          - CNNFashion_Mnist
          - CNNCifar
          - ModelBased
"""
import copy

import torch
import torch.nn as nn
import torch.nn.functional as F

from src.utils import log


def initialize_models(args, same=False, device='cpu'):
    # INITIALIZE PEERS MODELS
    models = []
    modelClass = None
    if args.model == 'cnn':
        # Convolutional neural network
        if args.dataset == 'mnist':
            modelClass = CNNMnist
        elif args.dataset == 'fmnist':
            modelClass = CNNFashion_Mnist
        elif args.dataset == 'cifar':
            modelClass = CNNCifar
    elif args.model == 'mlp':
        # Multi-layer perceptron
        if args.dataset == 'mnist':
            modelClass = FFNMnist
        else:
            modelClass = MLP
    elif args.model == 'linear':
        modelClass = LogisticRegression
    else:
        exit('Error: unrecognized model')

    if same:
        # Initialize all models with same weights
        model = None
        if args.model == 'cnn':
            model = modelClass(args=args)
        else:
            len_in = 28 * 28
            model = modelClass(dim_in=len_in, dim_out=args.num_classes)
        for i in range(args.num_users):
            models.append(copy.deepcopy(model))
        return models

    else:
        # Independent initialization
        for i in range(args.num_users):
            model = None
            if args.model == 'cnn':
                model = modelClass(args=args)
            else:
                len_in = 28 * 28
                model = modelClass(dim_in=len_in, dim_out=args.num_classes)
            models.append(model)

    for model in models:
        model.to(device)

    return models


# -- Base Model ---------------------------------------------------------------

class ModelBase(nn.Module):
    """Shared methods between models"""

    def __init__(self):
        super().__init__()

    def forward(self, xb):
        # Flatten the image tensors and do a forward pass
        flatten = xb.view(xb.size(0), -1)
        return self.network(flatten)

    def train_step(self, batch, device='cpu'):
        # Generate predictions and calculate loss
        images, labels = batch
        images, labels = images.to(device), labels.to(device)
        out = self(images)
        # loss = F.cross_entropy(out, labels).to(device)
        criterion = nn.CrossEntropyLoss()
        criterion = criterion.to(device)
        loss = criterion(out, labels)
        return loss

    def validation_step(self, batch, device='cpu'):
        images, labels = batch
        images, labels = images.to(device), labels.to(device)
        out = self(images)
        loss = F.cross_entropy(out, labels).to(device)
        acc = self.accuracy(out, labels)
        return {'val_loss': loss, 'val_acc': acc}

    def validation_epoch_end(self, outputs):
        # calculate mean loss and accuracy of one epoch
        batch_losses = [x['val_loss'] for x in outputs]
        epoch_loss = torch.stack(batch_losses).mean()
        batch_accs = [x['val_acc'] for x in outputs]
        epoch_acc = torch.stack(batch_accs).mean()
        return {'val_loss': epoch_loss.item(), 'val_acc': epoch_acc.item()}

    def epoch_end(self, epoch, result):
        log('', "Epoch [{}], val_loss: {:.4f}, val_acc: {:.4f}".format(epoch, result['val_loss'], result['val_acc']))

    def accuracy(self, outputs, labels):
        _, preds = torch.max(outputs, dim=1)
        return torch.tensor(torch.sum(preds == labels).item() / len(preds))

    def evaluate(self, val_loader, device='cpu', one_batch=False):
        if one_batch:
            batch = next(iter(val_loader))
            outputs = [self.validation_step(batch, device)]
        else:
            outputs = [self.validation_step(batch, device) for batch in val_loader]
        return self.validation_epoch_end(outputs)


#  Model Modules --------------------------------------------------------------


class FFNMnist(ModelBase):
    def __init__(self, dim_in, dim_out):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(dim_in, 16),
            nn.ReLU(),
            nn.Linear(16, 32),
            nn.ReLU(),
            nn.Linear(32, dim_out),
        )

    def forward(self, xb):
        # Flatten the image tensors and do a forward pass
        xb = xb.view(xb.size(0), -1)
        return self.network(xb)


class LogisticRegression(ModelBase):
    def __init__(self, dim_in, dim_out):
        super(LogisticRegression, self).__init__()

        self.linear = torch.nn.Linear(dim_in, dim_out)

    def forward(self, x):
        # Flatten the image tensors and do a forward pass
        x = x.view(x.size(0), -1)
        outputs = self.linear(x)
        return outputs


class MLP(ModelBase):
    def __init__(self, dim_in, dim_out):
        super(MLP, self).__init__()
        dim_hidden = 32
        self.layer_input = nn.Linear(dim_in, dim_hidden)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout()
        self.layer_hidden = nn.Linear(dim_hidden, dim_out)
        self.softmax = nn.Softmax(dim=1)

    def forward(self, x):
        x = x.view(-1, x.shape[1] * x.shape[-2] * x.shape[-1])
        x = self.layer_input(x)
        x = self.dropout(x)
        x = self.relu(x)
        x = self.layer_hidden(x)
        return self.softmax(x)


class CNNMnist(ModelBase):
    def __init__(self, args):
        super(CNNMnist, self).__init__()
        self.conv1 = nn.Conv2d(args.num_channels, 10, kernel_size=5)
        self.conv2 = nn.Conv2d(10, 20, kernel_size=5)
        self.conv2_drop = nn.Dropout2d()
        self.fc1 = nn.Linear(320, 50)
        self.fc2 = nn.Linear(50, args.num_classes)

    def forward(self, x):
        x = F.relu(F.max_pool2d(self.conv1(x), 2))
        x = F.relu(F.max_pool2d(self.conv2_drop(self.conv2(x)), 2))
        x = x.view(-1, x.shape[1] * x.shape[2] * x.shape[3])
        x = F.relu(self.fc1(x))
        x = F.dropout(x, training=self.training)
        x = self.fc2(x)
        return F.log_softmax(x, dim=1)


class CNNFashion_Mnist(ModelBase):
    def __init__(self, args):
        super(CNNFashion_Mnist, self).__init__()
        self.layer1 = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=5, padding=2),
            nn.BatchNorm2d(16),
            nn.ReLU(),
            nn.MaxPool2d(2))
        self.layer2 = nn.Sequential(
            nn.Conv2d(16, 32, kernel_size=5, padding=2),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2))
        self.fc = nn.Linear(7 * 7 * 32, 10)

    def forward(self, x):
        out = self.layer1(x)
        out = self.layer2(out)
        out = out.view(out.size(0), -1)
        out = self.fc(out)
        return out


class CNNCifar(ModelBase):
    def __init__(self, args):
        super(CNNCifar, self).__init__()
        self.conv1 = nn.Conv2d(3, 6, 5)
        self.pool = nn.MaxPool2d(2, 2)
        self.conv2 = nn.Conv2d(6, 16, 5)
        self.fc1 = nn.Linear(16 * 5 * 5, 120)
        self.fc2 = nn.Linear(120, 84)
        self.fc3 = nn.Linear(84, args.num_classes)

    def forward(self, x):
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = x.view(-1, 16 * 5 * 5)
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = self.fc3(x)
        return F.log_softmax(x, dim=1)
