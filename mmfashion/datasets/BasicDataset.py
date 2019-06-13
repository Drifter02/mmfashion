from functools import partial

import shutil
import time
import logging

import torch
import torch.nn as nn
import torch.nn.parallel
import torch.backends.cudnn as cudnn
import torch.optim
import torch.utils.data
from torch.utils.data.dataset import Dataset
import torchvision.transforms as transforms
import torchvision.datasets as datasets
import torchvision.models as models
import torch.nn.functional as F
from torch.utils.data import DataLoader

from mmcv.runner import get_dist_info
from mmcv.parallel import collate

import os
import sys
from skimage import io
from PIL import Image
import numpy as np

from .loader import GroupSampler, DistributedGroupSampler, DistributedSampler

class BasicDataset(Dataset):
    def __init__(self, img_path, img_file, label_file, bbox_file, landmark_file, img_size):
       self.img_path = img_path
       
       normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                         std=[0.229, 0.224, 0.225])
       self.transform = transforms.Compose([
            transforms.RandomResizedCrop(224),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            normalize,
       ])
 
       # read img names
       fp = open(img_file, 'r')
       self.img_list = [x.strip() for x in fp]
       fp.close()

       # read labels
       self.labels = np.loadtxt(label_file, dtype=np.float32)
       
       self.img_size = img_size
       
       # load bbox
       if bbox_file:
          self.with_bbox = True
          self.bboxes = np.loadtxt(bbox_file, usecols=(0,1,2,3))
       else:
          self.with_bbox = False
          self.bboxes = None
   
       # load landmarks
       if landmark_file:
          self.landmarks = np.loadtxt(landmark_file)
       else:
          self.landmarks = None

    def __getitem__(self, idx):
      img = Image.open(os.path.join(self.img_path, self.img_list[idx]))
      width, height = img.size
      if self.with_bbox:
         bbox_cor = self.bboxes[idx]
         x1 = max(0, int(bbox_cor[0])-10)
         y1 = max(0, int(bbox_cor[1])-10)
         x2 = int(bbox_cor[2])+10
         y2 = int(bbox_cor[3])+10
         bbox_w = x2-x1
         bbox_h = y2-y1      
         img = img.crop(box=(x1,y1,x2,y2))
      else:
         bbox_w, bbox_h = self.img_size[0], self.img_size[1]

      img.thumbnail(self.img_size, Image.ANTIALIAS)
      img = img.convert('RGB')
      img = self.transform(img)
  
      label = torch.from_numpy(self.labels[idx])
      landmark = []
      # compute the shifted variety
      origin_landmark = self.landmarks[idx]
      for i, l in enumerate(origin_landmark):
          if i%2==0: # x
             l_x = max(0, l-x1)
             l_x = float(l_x)/width * self.img_size[0]
             landmark.append(l_x) 
          else: # y
             l_y = max(0, l-y1)
             l_y = float(l_y)/height * self.img_size[1]
             landmark.append(l_y)
      #cnt = len(landmark)
      #while cnt<16:
      #   landmark.append(0)
      #   cnt = len(landmark)
      landmark = torch.from_numpy(np.array(landmark)).float()
       
      return img, label, landmark

    def __len__(self):
        return len(self.img_list)



#train_loader = BasicDataLoader(batch_size=16, num_workers=4).train_loader
#print('training data loaded')
#test_loader = BasicDataLoader(batch_size=16, num_workers=4).test_loader
#print('testing data loaded')