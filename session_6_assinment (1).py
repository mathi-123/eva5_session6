# -*- coding: utf-8 -*-
"""Session_6_Assinment.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1Fv9COLbSU5bGIRGOTDddtGNmooTkr2U5
"""



from google.colab import drive
drive.mount("/content/drive")

base_folder = 'drive/My Drive/file_from_colab/s6/'
acc_recorder_file = "highest_accuracy_achieved"
model_file_name = "reg_"

# Commented out IPython magic to ensure Python compatibility.
from __future__ import print_function
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torchvision import datasets, transforms

from operator import itemgetter
import time

from tqdm import tqdm

import matplotlib.pyplot as plt
# %matplotlib inline

# Train Phase transformations
train_transforms = transforms.Compose([
                                       transforms.RandomRotation((-5.0, 5.0), fill=(1,)),
                                       transforms.ToTensor(),
                                       transforms.Normalize((0.1307,), (0.3081,)) # The mean and std have to be sequences (e.g., tuples), therefore you should add a comma after the values. 
                                       # Note the difference between (0.1307) and (0.1307,) as this is one channel image, we have added one tuple for mean and std each 
                                       ])

# Test Phase transformations
test_transforms = transforms.Compose([
                                       transforms.ToTensor(),
                                       transforms.Normalize((0.1307,), (0.3081,))
                                       ])

train = datasets.MNIST('./data', train=True, download=True, transform=train_transforms)
test = datasets.MNIST('./data', train=False, download=True, transform=test_transforms)

"""# Dataset and Creating Train/Test Split - Extract part of ETL"""

train = datasets.MNIST('./data', train=True, download=True, transform=train_transforms)
test = datasets.MNIST('./data', train=False, download=True, transform=test_transforms)

"""
# Dataloader Arguments & Test/Train Dataloaders - Load part of ETL
"""

SEED = 1

# CUDA?
cuda = torch.cuda.is_available()
print("CUDA Available?", cuda)

# For reproducibility
torch.manual_seed(SEED)

if cuda:
    torch.cuda.manual_seed(SEED)

# dataloader arguments - something you'll fetch these from cmdprmt
dataloader_args = dict(shuffle=True, batch_size=128, num_workers=4, pin_memory=True) if cuda else dict(shuffle=True, batch_size=64)

# train dataloader
train_loader = torch.utils.data.DataLoader(train, **dataloader_args)

# test dataloader
test_loader = torch.utils.data.DataLoader(test, **dataloader_args)

"""# Model Architecture"""

class BatchNorm(nn.BatchNorm2d):
    def __init__(self, num_features, eps=1e-05, momentum=0.1, weight=True, bias=True):
        super().__init__(num_features, eps=eps, momentum=momentum)
        self.weight.data.fill_(1.0)
        self.bias.data.fill_(0.0)
        self.weight.requires_grad = weight
        self.bias.requires_grad = bias

class GhostBatchNorm(BatchNorm):
    def __init__(self, num_features, num_splits, **kw):
        super().__init__(num_features, **kw)
        self.num_splits = num_splits
        self.register_buffer('running_mean', torch.zeros(num_features * self.num_splits))
        self.register_buffer('running_var', torch.ones(num_features * self.num_splits))

    def train(self, mode=True):
        if (self.training is True) and (mode is False):  # lazily collate stats when we are going to use them
            self.running_mean = torch.mean(self.running_mean.view(self.num_splits, self.num_features), dim=0).repeat(
                self.num_splits)
            self.running_var = torch.mean(self.running_var.view(self.num_splits, self.num_features), dim=0).repeat(
                self.num_splits)
        return super().train(mode)

    def forward(self, input):
        N, C, H, W = input.shape
        if self.training or not self.track_running_stats:
            return F.batch_norm(
                input.view(-1, C * self.num_splits, H, W), self.running_mean, self.running_var,
                self.weight.repeat(self.num_splits), self.bias.repeat(self.num_splits),
                True, self.momentum, self.eps).view(N, C, H, W)
        else:
            return F.batch_norm(
                input, self.running_mean[:self.num_features], self.running_var[:self.num_features],
                self.weight, self.bias, False, self.momentum, self.eps)

import torch.nn.functional as F
dropout_value = 0.1
num_of_splits = 2
class Net(nn.Module):
    def __init__(self, is_gbn=False):
        super(Net, self).__init__()
        # Input Block
        self.convblock1 = nn.Sequential(
            nn.Conv2d(in_channels=1, out_channels=8, kernel_size=(3, 3), padding=0, bias=False),
            nn.ReLU(),
            nn.BatchNorm2d(8) if is_gbn == False else GhostBatchNorm(8,num_of_splits),
            nn.Dropout(dropout_value)
        ) # output_size = 26

        # CONVOLUTION BLOCK 1
        self.convblock2 = nn.Sequential(
            nn.Conv2d(in_channels=8, out_channels=16, kernel_size=(3, 3), padding=1, bias=False),
            nn.ReLU(),
            nn.BatchNorm2d(16) if is_gbn == False else GhostBatchNorm(16,num_of_splits),
            nn.Dropout(dropout_value)
        ) # output_size = 26

        # TRANSITION BLOCK 1
        self.convblock3 = nn.Sequential(
            nn.Conv2d(in_channels=16, out_channels=8, kernel_size=(1, 1), padding=0, bias=False),
        ) # output_size = 26
        self.pool1 = nn.MaxPool2d(2, 2) # output_size = 13

        # CONVOLUTION BLOCK 2
        self.convblock4 = nn.Sequential(
            nn.Conv2d(in_channels=8, out_channels=16, kernel_size=(3, 3), padding=0, bias=False),
            nn.ReLU(),            
            nn.BatchNorm2d(16) if is_gbn == False else GhostBatchNorm(16,num_of_splits),
            nn.Dropout(dropout_value)
        ) # output_size = 11
        self.convblock5 = nn.Sequential(
            nn.Conv2d(in_channels=16, out_channels=16, kernel_size=(3, 3), padding=0, bias=False),
            nn.ReLU(),            
            nn.BatchNorm2d(16) if is_gbn == False else GhostBatchNorm(16,num_of_splits),
            nn.Dropout(dropout_value)
        ) # output_size = 9
        self.convblock6 = nn.Sequential(
            nn.Conv2d(in_channels=16, out_channels=32, kernel_size=(3, 3), padding=0, bias=False),
            nn.ReLU(),            
            nn.BatchNorm2d(32) if is_gbn == False else GhostBatchNorm(32,num_of_splits),
            nn.Dropout(dropout_value)
        ) # output_size = 7

        # OUTPUT BLOCK
        self.gap = nn.Sequential(
            nn.AvgPool2d(kernel_size=7)
        ) # output_size = 1
        self.convblock7 = nn.Sequential(
            nn.Conv2d(in_channels=32, out_channels=10, kernel_size=(1, 1), padding=0, bias=False),
            # nn.BatchNorm2d(10),
            # nn.ReLU(),
            # nn.Dropout(dropout_value)
        ) 

    def forward(self, x):
        x = self.convblock1(x)
        x = self.convblock2(x)
        x = self.convblock3(x)
        x = self.pool1(x)
        x = self.convblock4(x)
        x = self.convblock5(x)
        x = self.convblock6(x)
        x = self.gap(x)        
        x = self.convblock7(x)

        x = x.view(-1, 10)
        return F.log_softmax(x, dim=-1)

"""# Model Summary"""

!pip install torchsummary
from torchsummary import summary
use_cuda = torch.cuda.is_available()
device = torch.device("cuda" if use_cuda else "cpu")
print(device)
model = Net().to(device)
summary(model, input_size=(1, 28, 28))



"""# **L1 Norm function**"""

def calculate_l1_reg(model, lambda_l1):
  """Calculate L1 Norm"""
  l1 = 0
  for p in model.parameters():
    l1 = l1 + p.abs().sum()
  return(lambda_l1*l1)

#Train and Test Functions

train_losses = []
train_acc = []

def train(model, device, train_loader, optimizer, epoch, m_num, lambda_l1):

  model.train()
  pbar = tqdm(train_loader)
  correct = 0
  processed = 0
  for batch_idx, (data, target) in enumerate(pbar):

    data, target = data.to(device), target.to(device)     # Get batch
    optimizer.zero_grad() # Set the gradients to zero before starting to do backpropragation
    y_pred = model(data)  # Predict

    loss = F.nll_loss(y_pred, target) # Calculate loss

    if m_num in {0,2,4}:
      # Calculate the MSE and L1 
      l1 = calculate_l1_reg(model, lambda_l1)
      loss = loss + l1
      
    train_losses.append(loss) # Accumulate loss per batch

    # Backpropagation
    loss.backward()
    optimizer.step()

    # Update pbar-tqdm
    pred = y_pred.argmax(dim=1, keepdim=True)  # get the index of the max log-probability
    correct += pred.eq(target.view_as(pred)).sum().item()
    processed += len(data)

    pbar.set_description(desc= f'Loss={loss.item()} Batch_id={batch_idx} Train Accuracy={100*correct/processed:0.2f}')
    train_acc.append(100*correct/processed)

  return loss.item(), 100*correct/processed, train_losses, train_acc

test_losses = []
test_acc = []
def test(model, device, test_loader):

  model.eval()
  test_loss = 0
  correct = 0
  with torch.no_grad():
      for data, target in test_loader:
          data, target = data.to(device), target.to(device)
          output = model(data)
          test_loss += F.nll_loss(output, target, reduction='sum').item()  # sum up batch loss
          pred = output.argmax(dim=1, keepdim=True)  # get the index of the max log-probability
          correct += pred.eq(target.view_as(pred)).sum().item()

  test_loss /= len(test_loader.dataset)
  test_losses.append(test_loss)

  print('\nTest set: Average loss: {:.4f}, Test Accuracy: {}/{} ({:.2f}%)\n'.format(
      test_loss, correct, len(test_loader.dataset),
      100. * correct / len(test_loader.dataset)))
  
  test_acc.append(100. * correct / len(test_loader.dataset))

  return test_loss, 100. * correct / len(test_loader.dataset), test_losses, test_acc

def record_max_acc(max_acc):
  f = open(base_folder+acc_recorder_file, "w")
  f.write(str(max_acc))
  f.close()

from torch.optim.lr_scheduler import StepLR
model_dict = {0:'L1_BN', 1:'L2_BN', 2:'L1_L2_BN', 3:'GBN', 4:'L1_L2_GBN'}
tr_ls_dict = {0:[], 1:[], 2:[], 3:[], 4:[]}
ts_ls_dict = {0:[], 1:[], 2:[], 3:[], 4:[]}
tr_acc_dict = {0:[], 1:[], 2:[], 3:[], 4:[]}
ts_acc_dict = {0:[], 1:[], 2:[], 3:[], 4:[]}

MODELS = 5
for m_num in range(MODELS):
  train_losses = []
  train_acc = []
  test_losses = []
  test_acc = []
  max_acc = 0.0
  if m_num in {3,4}:
    model =  Net(is_gbn=True).to(device)
  else:  
    model =  Net().to(device)
  if m_num in {1,2,4}: # Apply L2 Norm
    optimizer = optim.SGD(model.parameters(), lr=0.1, momentum=0.9,weight_decay=1e-4)
    scheduler = StepLR(optimizer, step_size=5, gamma=0.1)
  else: 
    optimizer = optim.SGD(model.parameters(), lr=0.1, momentum=0.9)
    scheduler = StepLR(optimizer, step_size=5, gamma=0.1)
  print(f'Model Name: ==================( {model_dict[m_num]} )==================')

try:
  with open(base_folder+acc_recorder_file, "r") as infl:
      max_acc = float(infl.read().strip())
except:
  max_acc = 0.0

EPOCHS = 25
for epoch in range(EPOCHS):
  print("EPOCH:", epoch)
  tr_loss, tr_acc, tr_ls_dict[m_num], tr_acc_dict[m_num] = train(model, device, train_loader, optimizer, epoch, m_num, lambda_l1=1e-5)
    
  scheduler.step()
  tst_loss, tst_acc, ts_ls_dict[m_num], ts_acc_dict[m_num] = test(model, device, test_loader)

  if m_num == 3 and tst_acc > max_acc: # Store GBN Model
    max_acc = tst_acc
    torch.save(model.state_dict(), base_folder+model_file_name+model_dict[m_num]+"_sd.pth")
    record_max_acc(max_acc)

print(f'Maximum Test Accuracy for {model_dict[m_num]} is {tst_acc}')
print('=========================================================')



"""# **Graph to show the validation accuracies and loss change curves for all 5 Models**

"""

plt.style.use('ggplot')

fig, axs = plt.subplots(2,2,figsize=(30,20))
for m_num in range(MODELS):
  axs[0, 0].plot(tr_ls_dict[m_num],label=model_dict[m_num] )
  axs[0, 0].legend(loc="upper right")
  axs[0, 0].set_title("Training Loss")
  axs[1, 0].plot(tr_acc_dict[m_num],label=model_dict[m_num])
  axs[1, 0].legend(loc="lower right")
  axs[1, 0].set_title("Training Accuracy")
  axs[0, 1].plot(ts_ls_dict[m_num],label=model_dict[m_num])
  axs[0, 1].legend(loc="upper right")
  axs[0, 1].set_title("Test Loss")
  axs[1, 1].plot(ts_acc_dict[m_num],label=model_dict[m_num])
  axs[1, 1].legend(loc="lower right")
  axs[1, 1].set_title("Test Accuracy")

"""
# **Check for incorrectly classified images**
"""

l1_model = Net(is_gbn=True)
model_file_name = 'l1_norm'
#l1_model.load_state_dict(torch.load(base_folder+model_file_name+"GBN_sd.pth")) # Load GBN Model
l1_model.load_state_dict(torch.load("/content/drive/MyDrive/file_from_colab/s6/l1_norm_GBN_sd.pth")) # Load GBN Model#
#/content/drive/MyDrive/eva5_stored_from_colab/s6
imgs = []
labels = []
preds = []
for img, target in test_loader:
  imgs.append( img )
  labels.append( target )
  preds.append( torch.argmax(l1_model(img), dim=1) )

imgs = torch.cat(imgs, dim=0)
labels = torch.cat(labels, dim=0)
preds = torch.cat(preds, dim=0)

matches = preds.eq(labels)

!ls drive/'My Drive'/file_colab/s6/l1_normGBN_sd.pth
'drive/My Drive/eva5_stored_from_colab/s6/l1_normGBN_sd.pth'

def create_plot_pos(nrows, ncols):
  num_images = nrows * ncols
  positions = []
  for r in range(num_images):
    row = r // ncols
    col = r % ncols
    positions.append((row, col))
  return positions

idx = 0
nrows = 5
ncols = 5
skip = 25

total_imgs = nrows*ncols
pos = create_plot_pos(5, 5)

fig, axes = plt.subplots(nrows=5, ncols=5, figsize=(15, 10), sharex=True, sharey=True)

idx = 0
posidx = 0
total_skipped = 0
for m in matches:
  if posidx > total_imgs-1:
    break

  if not m:
    if total_skipped <= skip:
      total_skipped += 1
      idx += 1
      continue

    img = imgs[idx].reshape(28,28)
    title = "Act: " + str(labels[idx].item()) + ", Pred: " + str(preds[idx].item())
    chart_pos = pos[posidx]
    axes[chart_pos].imshow(img)
    axes[chart_pos].set_title(title)
    axes[chart_pos].axis("off")

    posidx += 1
    idx += 1

