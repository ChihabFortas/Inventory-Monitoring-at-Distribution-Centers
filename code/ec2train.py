import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import torchvision
import torchvision.models as models
import torchvision.transforms as transforms

import copy
import argparse
import os
import logging
import sys
from tqdm import tqdm
from PIL import ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True

logger=logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))


def train(model, train_loader, validation_loader, criterion, optimizer, epochs, device):
    best_loss=1e6
    image_dataset={'train':train_loader, 'valid':validation_loader}
    loss_counter=0
    log = Report(epochs)

    for epoch in range(epochs):
        for phase in ['train', 'valid']:
            if phase=='train':
                model.train()
            else:
                model.eval()
            running_loss = 0.0
            running_corrects = 0

            for pos,(inputs, labels) in enumerate(image_dataset[phase]):
                inputs = inputs.to(device)
                labels = labels.to(device)
                tot=len(image_dataset[phase])
                outputs = model(inputs)
                loss = criterion(outputs, labels)

                if phase=='train':
                    optimizer.zero_grad()
                    loss.backward()
                    log.record(pos=(pos+1)/tot, train_loss=loss, end='\r') # impersistent data
                    optimizer.step()

                _, preds = torch.max(outputs, 1)
                running_loss += loss.item() * inputs.size(0)
                running_corrects += torch.sum(preds == labels.data)

            epoch_loss = running_loss / len(image_dataset[phase])
            epoch_acc = running_corrects / len(image_dataset[phase])
            
            if phase=='valid':
                if epoch_loss<best_loss:
                    best_loss=epoch_loss
                else:
                    loss_counter+=1
                with torch.no_grad():
                    for pos,(inputs, labels) in enumerate(image_dataset[phase]):
                        tot=len(image_dataset[phase])
                        outputs = model(inputs)
                        valid_loss = criterion(outputs, labels)
                        logger.info('{} loss: {:.4f}, acc: {:.4f}, best loss: {:.4f}'.format(phase,
                                                                                             epoch_loss,
                                                                                             epoch_acc,
                                                                                             best_loss))

        if loss_counter==1:
            break
        if epoch==0:
            break
    return model
    
def test(model, test_loader, criterion, device):
    model.eval()
    running_loss=0
    running_corrects=0
    
    for inputs, labels in test_loader:
        inputs=inputs.to(device)
        labels=labels.to(device)
        outputs=model(inputs)
        loss=criterion(outputs, labels)
        _, preds = torch.max(outputs, 1)
        running_loss += loss.item() * inputs.size(0)
        running_corrects += torch.sum(preds == labels.data)

    total_loss = running_loss / len(test_loader)
    total_acc = running_corrects.double() / len(test_loader)
    logger.info(f"Testing Loss: {total_loss}")
    logger.info(f"Testing Accuracy: {total_acc}")
    

def net():
    model = models.resnet50(pretrained=True)

    for param in model.parameters():
        param.requires_grad = False   

    n_features = model.fc.in_features

    model.fc = nn.Sequential(
                   nn.Linear(n_features, 128),
                   nn.ReLU(inplace=True),
                   nn.Linear(128, 32),
                   nn.ReLU(inplace=True),        
                   nn.Linear(128, 5))
    return model

def create_data_loaders(data, batch_size):
    train_data_path = os.path.join(data, 'train')
    test_data_path = os.path.join(data, 'test')
    validation_data_path=os.path.join(data, 'valid')

    train_transform = transforms.Compose([
        transforms.RandomResizedCrop((224, 224)),
        transforms.RandomHorizontalFlip(p=0.1),
        transforms.RandomGrayscale(p=0.1),
        transforms.RandomApply([transforms.ColorJitter(0.5, 0.5, 0.5, 0.5)]),
        transforms.ToTensor(),
        ])

    test_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        ])

    train_data = torchvision.datasets.ImageFolder(root=test_data_path, transform=train_transform)
    train_data_loader = torch.utils.data.DataLoader(train_data, batch_size=batch_size, shuffle=True)

    test_data = torchvision.datasets.ImageFolder(root=test_data_path, transform=test_transform)
    test_data_loader  = torch.utils.data.DataLoader(test_data, batch_size=batch_size, shuffle=True)

    validation_data = torchvision.datasets.ImageFolder(root=validation_data_path, transform=test_transform)
    validation_data_loader  = torch.utils.data.DataLoader(validation_data, batch_size=batch_size, shuffle=True) 
    
    return train_data_loader, test_data_loader, validation_data_loader

def main(args):

    logger.info(f'Training with : {args.learning_rate}, Batch Size: {args.batch_size}, epochs: {args.epochs}')
    logger.info(f'Data Paths: {args.data}')

    # Hyperparameters 
    batch_size=args.batch_size
    learning_rate=args.learning_rate
    epochs = args.epochs

    #Create dataLoaders and Model
    train_loader, test_loader, validation_loader = create_data_loaders(args.data, batch_size)

    model=net()

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.fc.parameters(), lr=learning_rate)

    logger.info("Starting Model Training")
    model=train(model, train_loader, validation_loader, criterion, optimizer, epochs, device)

    logger.info("Starting Model Testing ")
    test(model, test_loader, criterion, device)

    logger.info("Saving the Model")
    torch.save(model.state_dict(), args.output_dir)
    print('saved')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--learning_rate', type=float)
    parser.add_argument('--batch_size', type=int)
    parser.add_argument('--epochs', type=int)
    parser.add_argument('--data', type=str, default=os.environ['dogImages'])
    parser.add_argument('--output_dir', type=str, default=os.environ['TrainedModels/model.pth'])
    
    args=parser.parse_args()    
    main(args)
