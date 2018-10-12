import math
import numpy as np
import os
import sys
import time

import numpy as np
import mxnet
from mxnet import gpu
from mxnet import nd

import matplotlib
import matplotlib.pyplot as plt
import PIL

module_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(module_dir, '..'))
from pil_image_enhancement import *
import utils_gluon

matplotlib.use('TkAgg')

color = [(255,255,0), (255,0,255), (0,255,255),(0,0,255), 
	(0,255,0), (255,0,0), (0,0,0), (255,255,255)]
	
class AddLP():
	def __init__(self, img_h, img_w, class_index):
		self.class_index = int(class_index)
		self.h = img_h
		self.w = img_w
		self.BIL = PIL.Image.BILINEAR
		self.LP_WH = [[380, 160], [320, 150], [320, 150]]
		self.x = [np.array([7, 56, 106, 158, 175, 225, 274, 324]), 
				  np.array([7, 57, 109, 130, 177, 223, 269])]

		self.font0 = [None] * 35
		self.font1 = [None] * 35

		
		fonts_dir = os.path.join(module_dir, 'fonts')
		self.dot = PIL.Image.open(fonts_dir+"/34.png").resize((10, 70), self.BIL)
		for font_name in range(0, 34):
			f = PIL.Image.open(fonts_dir+'/'+str(font_name)+".png")
			self.font0[font_name] = f.resize((45, 90), self.BIL)
			self.font1[font_name] = f.resize((40, 80), self.BIL)
		
		self.pil_image_enhance = PILImageEnhance(M=.1, N=.2, R=20.0, G=0.3, noise_var=20.)
		self.augs = mxnet.image.CreateAugmenter(data_shape=(3, self.h, self.w),	
			inter_method=10, brightness=0.5, contrast=0.5, saturation=0.5, pca_noise=1.0)
		self.augs2 = mxnet.image.CreateAugmenter(data_shape=(3, self.h, self.w),	
			inter_method=10, brightness=0.5, contrast=0.5, saturation=0.5, pca_noise=1.0)

	def draw_LP(self):
		LP_type = np.random.randint(2)
		LP_w, LP_h = self.LP_WH[LP_type]
		x = self.x[LP_type]
		label = []
		if LP_type == 0: # ABC-1234
			LP = PIL.Image.new('RGBA', (LP_w, LP_h), color[7])
			abc = np.random.randint(10, 34, size=3)
			for i, j in enumerate(abc): 
				LP.paste(self.font0[j], (x[i], 35))
				label.append([j, float(x[i])/LP_w, float(x[i]+45)/LP_w])

			LP.paste(self.dot,(x[3], 45))

			num = np.random.randint(0, 10, size=4)
			for i, j in  enumerate(num): 
				LP.paste(self.font0[j], (x[i+4], 35)) 
				label.append([j, float(x[i+4])/LP_w, float(x[i+4]+45)/LP_w])

		if LP_type == 1: # AB-1234
			LP = PIL.Image.new('RGBA', (LP_w, LP_h), color[7])
			abc = np.random.randint(10, 34, size=2)
			for i, j in enumerate(abc): 
				LP.paste(self.font1[j], (x[i], 40))
				label.append([j, float(x[i])/LP_w, float(x[i]+40)/LP_w])

			LP.paste(self.dot,(x[2], 45))

			num = np.random.randint(0, 10, size=4)
			for i, j in  enumerate(num): 
				LP.paste(self.font1[j], (x[i+3], 40))
				label.append([j, float(x[i+3])/LP_w, float(x[i+3]+40)/LP_w])

		return LP, label
	
	def resize_and_paste_LP(self, LP, OCR_labels=None):
		# print(LP.size[0], LP.size[1]) # (320, 150)
		resize_w = int((np.random.rand()*0.15+0.15)*LP.size[0])
		resize_h = int((np.random.rand()*0.1+0.2)*LP.size[1])
		LP = LP.resize((resize_w, resize_h), self.BIL)

		LP, r = self.pil_image_enhance(LP)

		paste_x = int(np.random.rand() * (self.w-120))
		paste_y = int(np.random.rand() * (self.h-120))
		
		tmp = PIL.Image.new('RGBA', (self.w, self.h))
		tmp.paste(LP, (paste_x, paste_y))

		m = nd.array(tmp.split()[-1]).reshape(1, self.h, self.w)
		mask = nd.tile(m, (3,1,1))

		LP = PIL.Image.merge("RGB", (tmp.split()[:3]))
		LP = nd.array(LP)
		LP_ltrb = tmp.getbbox()
		LP_label = nd.array(LP_ltrb)

		if OCR_labels is not None:
			print('TODO')
			#TODO
		else:
			for aug in self.augs: LP = aug(LP)
			LP_label = nd.array([[
				self.class_index, 
				float(LP_ltrb[0])/self.w, 
				float(LP_ltrb[1])/self.h, 
				float(LP_ltrb[2])/self.w, 
				float(LP_ltrb[3])/self.h, 
				0 # i dot car Licence plate rotating 
			]])

			return LP.transpose((2,0,1)), mask, LP_label

	def add(self, img_batch, label_batch):
		ctx = label_batch.context
		bs = label_batch.shape[0]
		h = img_batch.shape[2]
		w = img_batch.shape[3]
		
		LP_label_batch = nd.zeros((bs,1,6), ctx=ctx)
		LP_image_batch = nd.zeros((bs,3,h,w), ctx=ctx)
		LP_mask_batch = nd.zeros((bs,3,h,w), ctx=ctx)

		for i in  range(bs):
			LP, _ = self.draw_LP()
			LP_image, LP_mask, LP_label = self.resize_and_paste_LP(LP)

			LP_mask_batch[i] = LP_mask
			LP_image_batch[i] = LP_image
			LP_label_batch[i] = LP_label

		img_batch = nd.where(LP_mask_batch<200, img_batch, LP_image_batch)
		img_batch = nd.clip(img_batch, 0, 1)

		LP_label_batch[:,:,1:5] = utils_gluon.nd_label_batch_ltrb2yxhw(LP_label_batch[:,:,1:5])
		label_batch = nd.concat(label_batch, LP_label_batch, dim=1)

		return img_batch, label_batch

	def render(self, bs, ctx):
		LP_label = nd.ones((bs,7,5), ctx=ctx) * -1
		LP_batch = nd.zeros((bs,3,self.h,self.w), ctx=ctx)
		mask = nd.zeros((bs,3,self.h,self.w), ctx=ctx)
		
		for i in range(bs):
			
			LP, LP_w, LP_h, labels = self.draw_LP()

			resize = np.random.rand() * 0.1 + 0.9
			LP_w = int(resize * self.w)
			LP_h = int((np.random.rand()*0.1+0.9) * resize * self.h)
			LP = LP.resize((LP_w, LP_h), self.BIL)

			LP, r = img_enhance(LP, M=.0, N=.0,R=5.0, G=8.0)
			#LP = LP.filter(ImageFilter.GaussianBlur(radius=np.random.rand()*8.))

			paste_x = np.random.randint(int(-0.0*LP_w), int(self.w-LP_w))
			paste_y = np.random.randint(int(-0.0*LP_h), int(self.h-LP_h))

			tmp = PIL.Image.new('RGBA', (self.w, self.h))
			tmp.paste(LP, (paste_x, paste_y))
			bg = PIL.Image.new('RGBA', (self.w, self.h), tuple(np.random.randint(255,size=3)))
			LP = PIL.Image.composite(tmp, bg, tmp)

			LP = nd.array(PIL.Image.merge("RGB", (LP.split()[:3])))
			for aug in self.augs2: LP = aug(LP)

			LP_batch[i] = LP.as_in_context(ctx).transpose((2,0,1))/255.

			r = r*np.pi/180
			offset = paste_x + abs(LP_h*math.sin(r)/2)
			for j,c in enumerate(labels):

				LP_label[i,j,0] = c[0]
				LP_label[i,j,1] = (offset + c[1]*LP_w*math.cos(r))/self.w
				LP_label[i,j,3] = (offset + c[2]*LP_w*math.cos(r))/self.w
				#LP_label[i,j,1] = (c[1]*LP_w*math.cos(r) - 40*math.sin(r) + paste_x)/self.w
				#LP_label[i,j,3] = (c[2]*LP_w*math.cos(r) + 40*math.sin(r) + paste_x)/self.w
		LP_batch = nd.clip(LP_batch, 0, 1)

		return LP_batch, LP_label
	
	def test_render(self, n):	
		plt.ion()
		fig = plt.figure()
		ax = []
		for i in range(n):
			ax.append(fig.add_subplot(321+i))
		while True:
			img_batch, label_batch = self.render(n, gpu(0))
			for i in range(n):
				label = label_batch[i]
				s = self.label2nparray(label)
				ax[i].clear()
				ax[i].plot(range(8,384,16),(1-s)*160, 'r-')
				ax[i].imshow(img_batch[i].transpose((1,2,0)).asnumpy())

			raw_input('next')
	
	def label2nparray(self, label):
		score = nd.zeros((24))
		for L in label: # all object in the image
			if L[0] < 0: continue
			text_cent = ((L[3] + L[1])/2.)
			left = int(round((text_cent.asnumpy()[0]-15./self.w)*24))
			right = int(round((text_cent.asnumpy()[0]+15./self.w)*24))
			#left = int(round(L[1].asnumpy()[0]*24))
			#right = int(round(L[3].asnumpy()[0]*24))
			for ii in range(left, right):
				box_cent = (ii + 0.5) / 24.
				score[ii] = 1-nd.abs(box_cent-text_cent)/(L[3]-L[1])
		return score.asnumpy()
	
	def test_add(self,b):
		#while True:
		batch_iter = load(b, h, w)
		for batch in batch_iter:
			imgs = batch.data[0].as_in_context(ctx[0]) # b*RGB*w*h
			labels = batch.label[0].as_in_context(ctx[0]) # b*L*5
			#imgs = nd.zeros((b, 3, self.h, self.w), ctx=gpu(0))*0.5
			tic = time.time()
			imgs, labels = self.add(imgs/255, labels)
			#print(time.time()-tic)
			for i, img in enumerate(imgs):
				R,G,B = img.transpose((1,2,0)).split(num_outputs=3, axis=-1)
				img = nd.concat(B,G,R, dim=-1).asnumpy()
				print(labels[i])
				cv2.imshow('%d'%i, img)
			if cv2.waitKey(0) & 0xFF == ord('q'): break
