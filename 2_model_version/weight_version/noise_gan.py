
# coding: utf-8

# In[1]:


import os,sys
import random
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm_notebook as tqdm
from keras.models import Model
from keras.layers import Input, Reshape, Conv2DTranspose
from keras.layers.core import Dense, Activation, Dropout, Flatten
from keras.layers.normalization import BatchNormalization
from keras.layers.convolutional import UpSampling1D, Conv1D
from keras.layers.advanced_activations import LeakyReLU
from keras.optimizers import Adam, SGD
from keras.callbacks import TensorBoard
from scipy import signal, stats


# In[2]:

# set variables
n_total = 500
n_samples = int(n_total*0.5)
noise_samples = int(n_total*0.5)
noise_dim = 1
batch_size = 16
epochs = 2500
g_lr = 40e-4 #2e-4
d_lr = 40e-4 #6e-4
nstd = 1


def sample_data(n_samples=10000, x_vals=np.arange(0, 5, .1), max_offset=2*np.pi, mul_range=[1, 2]):
    vectors = []
    for i in range(n_samples):
        offset = np.random.random() * max_offset
        #mul = mul_range[0] + np.random.random() * (mul_range[1] - mul_range[0])
        mul = (2 * np.pi) / 5 
        vectors.append(
            np.sin(offset + x_vals * mul)
        )
    return np.array(vectors)

ax = pd.DataFrame(np.transpose(sample_data(25))).plot(legend=False)
ax = ax.get_figure()
plt.xlabel('Time')
plt.ylabel('Amplitude')
ax.savefig('/home/hunter.gabbard/public_html/Burst/Gauss_pulse_testing/input_waveforms.png')
plt.close(ax)


# In[4]:


def get_generative(G_in, dense_dim=128, drate=0.6, out_dim=50, lr=1e-3):
    # original network
    """
    x = Dense(512, activation='relu')(G_in)
    x = Dense(256, activation='relu')(x)
    x = BatchNormalization()(x)
    x = Dense(128, activation='relu')(x)
    x = BatchNormalization()(x)
    x = Dense(64, activation='relu')(x)
    x = BatchNormalization()(x)
    G_out = Dense(out_dim, activation='tanh')(x)
    G = Model(G_in, G_out)
    opt = SGD(lr=lr)
    G.compile(loss='binary_crossentropy', optimizer=opt)
    """

    # transpose convolutional network
    
    x = Reshape((-1,1,1))(G_in)
    x = BatchNormalization()(x) 
    x = Conv2DTranspose(128,(1,4),strides=(1,1),padding='valid',activation='relu')(x)
    x = BatchNormalization()(x)
    #x = Dropout(drate)(x)

    x = Conv2DTranspose(64,(1,8),strides=(1,1),padding='valid',activation='relu')(x)
    x = BatchNormalization()(x)
    #x = Dropout(drate)(x)

    x = Conv2DTranspose(32,(1,16),strides=(1,1),padding='valid',activation='relu')(x)
    x = BatchNormalization()(x)
    #x = Dropout(drate)(x)

    x = Conv2DTranspose(16,(1,32),strides=(1,1),padding='valid',activation='relu')(x)
    x = BatchNormalization()(x)
    #x = Dropout(drate)(x)

    x = Flatten()(x)
    x = BatchNormalization()(x)

    x = Dense(out_dim, activation='relu')(x)
    x = BatchNormalization()(x)
    #x = Dropout(drate)(x)

    G_out = Dense(out_dim, activation='linear')(x)
    #G_out = Conv2DTranspose(1,(1,out_dim))(x)
    G = Model(G_in, G_out)
    #opt = SGD(lr=lr)
    opt = Adam(lr=lr, beta_1=0.5)
    G.compile(loss='binary_crossentropy', optimizer=opt)
    

    return G, G_out

G_in = Input(shape=(1,noise_dim))
G, G_out = get_generative(G_in, lr=g_lr)
G.summary()


# In[3]:


def get_discriminative(D_in, lr=1e-3, drate=.6, n_channels=50, conv_sz=5, leak=.2):
    # old network
    
    """
    x = Reshape((-1, 1))(D_in)
    x = Conv1D(n_channels, conv_sz)(x)
    x = LeakyReLU(alpha=0.2)(x)
    x = Dropout(drate)(x)
    x = Flatten()(x)
    x = Dense(n_channels)(x)
    """    

    
    x = Reshape((-1, 1))(D_in)
    x = Conv1D(50, 16)(x)
    x = LeakyReLU(alpha=0.2)(x)
    #x = BatchNormalization()(x)
    #x = Dropout(drate)(x)
    #x = Conv1D(128, 8)(x)
    #x = LeakyReLU(alpha=0.2)(x)
    #x = BatchNormalization()(x)
    #x = Conv1D(256, 4)(x)
    #x = LeakyReLU(alpha=0.2)(x)
    #x = BatchNormalization()(x)
    #x = Conv1D(512, 4)(x)
    #x = LeakyReLU(alpha=0.2)(x)
    #x = BatchNormalization()(x)
    
    x = Flatten()(x)
    #x = BatchNormalization()(x)
    x = Dense(n_channels, activation='tanh')(x)
    #x = BatchNormalization()(x)
    D_out = Dense(2, activation='sigmoid')(x)
    #D_out = BatchNormalization()(D_out)
    D = Model(D_in, D_out)
    dopt = Adam(lr=lr, beta_1=0.5)
    D.compile(loss='binary_crossentropy', optimizer=dopt)
    return D, D_out

D_in = Input(shape=(50,))
D, D_out = get_discriminative(D_in, lr=d_lr)
D.summary()



# In[5]:


def set_trainability(model, trainable=False):
    model.trainable = trainable
    for layer in model.layers:
        layer.trainable = trainable
        
def make_gan(GAN_in, G, D):
    set_trainability(D, False)
    x = G(GAN_in)
    GAN_out = D(x)
    GAN = Model(GAN_in, GAN_out)
    GAN.compile(loss='binary_crossentropy', optimizer=G.optimizer)
    return GAN, GAN_out

GAN_in = Input((1,noise_dim))
GAN, GAN_out = make_gan(GAN_in, G, D)
GAN.summary()



# In[6]:


def sample_data_and_gen(G, noise_dim=10, n_samples=10000, noise_samples=100):
    XT = sample_data(n_samples=n_samples)
    XT = np.random.normal(0,nstd, size=[XT.shape[0], 1, XT.shape[1]]) 
    XN_noise = np.random.normal(0, 1, size=[noise_samples, 1, noise_dim])
    #XT = np.resize(XT, (XT.shape[0],1,XT.shape[1]))

    XN = G.predict(XN_noise / np.max(XN_noise))
    XT = np.resize(XT, (XT.shape[0],XT.shape[2]))
    X = np.vstack((XT, XN))
    y = np.zeros((n_samples+len(XN_noise), 2))
    y[:n_samples, 1] = 1
    y[n_samples:, 0] = 1
    return X, y

def pretrain(G, D, noise_dim=10, n_samples=10000, noise_samples=10000, batch_size=32):
    X, y = sample_data_and_gen(G, n_samples=n_samples, noise_samples=noise_samples, noise_dim=noise_dim)
    set_trainability(D, True)


    D.fit(X, y, epochs=1, batch_size=batch_size)

pretrain(G, D, n_samples=n_samples, noise_samples=noise_samples, noise_dim=noise_dim, batch_size=batch_size)

# In[ ]:


def sample_noise(G, noise_dim=10, n_samples=10000):
    X = np.random.normal(0, 1, size=[n_samples, 1, noise_dim])
    y = np.zeros((n_samples, 2))
    y[:, 1] = 1
    return X, y

def train(GAN, G, D, epochs=500, n_samples=10000, noise_samples=noise_samples, noise_dim=10, batch_size=32, verbose=False, v_freq=1):
    d_loss = []
    g_loss = []
    e_range = range(epochs)
    if verbose:
        e_range = tqdm(e_range)
    for epoch in e_range:

        # use experience replay
        """
        if epoch == 0:
            X, y = sample_data_and_gen(G, n_samples=n_samples, noise_samples=noise_samples, noise_dim=noise_dim)
            X_past, y_past = X, y
        elif epoch%5 == 0 and epoch > 0:
            X, y = sample_data_and_gen(G, n_samples=n_samples, noise_samples=noise_samples, noise_dim=noise_dim)
            X_past, y_past = X, y
            X = np.vstack((X[:int(len(X)/2),:],X_past[int(len(X_past)*(3/4)):,:],X[int(len(X)*(3/4)):,:]))
            y = np.vstack((y[:int(len(y)/2),:],y_past[int(len(y_past)*(3/4)):,:],y[int(len(y)*(3/4)):,:]))
        else:
            X, y = sample_data_and_gen(G, n_samples=n_samples, noise_samples=noise_samples, noise_dim=noise_dim)
        """

        X, y = sample_data_and_gen(G, n_samples=n_samples, noise_samples=noise_samples, noise_dim=noise_dim)

        # train networks
        set_trainability(D, True)
        d_loss.append(D.train_on_batch(X, y))
        
        X, y = sample_noise(G, n_samples=noise_samples, noise_dim=noise_dim)
        set_trainability(D, False)
        g_loss.append(GAN.train_on_batch(X, y))
        if verbose and (epoch + 1) % v_freq == 0:
            print("Epoch #{}: Generative Loss: {}, Discriminative Loss: {}".format(epoch + 1, g_loss[-1], d_loss[-1]))

    # save discrminator weights
    D.save_weights('best_d_weights.hdf5')
    D.save('d_model.hdf5')

    return d_loss, g_loss

d_loss, g_loss = train(GAN, G, D, epochs=epochs, n_samples=n_samples,
                       noise_samples=noise_samples, noise_dim=noise_dim, batch_size=batch_size, verbose=True)


# In[ ]:


ax = pd.DataFrame(
    {
        'Generative Loss': g_loss,
        'Discriminative Loss': d_loss,
    }
).plot(title='Training loss', logy=True)
ax.set_xlabel("Epochs")
ax.set_ylabel("Loss")
ax.set_yscale("log")
ax = ax.get_figure()
ax.savefig('/home/hunter.gabbard/public_html/Burst/Gauss_pulse_testing/loss.png')
plt.close(ax)


# In[ ]:


N_VIEWED_SAMPLES = 25
data_and_gen, _ = sample_data_and_gen(G, noise_samples=N_VIEWED_SAMPLES, n_samples=N_VIEWED_SAMPLES, noise_dim=noise_dim)
ax = pd.DataFrame(np.transpose(data_and_gen[N_VIEWED_SAMPLES:])).plot(legend=False,alpha=0.5)
ax = ax.get_figure()
plt.xlabel('Time')
plt.ylabel('Amplitude')
ax.savefig('/home/hunter.gabbard/public_html/Burst/Gauss_pulse_testing/gen_waveform.png')
plt.close(ax)

# return histogram of output distribution
#ax = pd.DataFrame(np.transpose(data_and_gen[N_VIEWED_SAMPLES:]))[0].hist()
#ax = ax.get_figure()
#ax.savefig('/home/hunter.gabbard/public_html/Burst/Gauss_pulse_testing/gen_hist.png')
#plt.close(ax)


# return histogram of output distribution
ax = pd.DataFrame(np.transpose(data_and_gen[N_VIEWED_SAMPLES:]))
for i in range(N_VIEWED_SAMPLES):
    #ax = pd.DataFrame(np.transpose(data_and_gen[N_VIEWED_SAMPLES:]))[0].hist(normed=True, bins=np.linspace(-3,3,10), histtype='step')
    #plt.plot(ax[i])
    plt.hist(ax[i], normed=True, bins=np.linspace(np.min(np.array(ax[i]).flatten()),np.max(np.array(ax[i]).flatten()),10), histtype='step')
    #ax = ax.get_figure()

ax_flatten = np.array(ax).flatten()
plt.hist(ax_flatten, color='k', normed=True, bins=np.linspace(np.min(ax_flatten),np.max(ax_flatten),25), histtype='step')
plt.plot(np.linspace(np.min(ax_flatten),np.max(ax_flatten),100), stats.norm.pdf(np.linspace(np.min(ax_flatten),np.max(ax_flatten),100), loc=0, scale=nstd), '--k')
plt.savefig('/home/hunter.gabbard/public_html/Burst/Gauss_pulse_testing/gen_hist.png')
plt.close()


plt.hist(ax_flatten, color='k', normed=True, bins=np.linspace(np.min(ax_flatten),np.max(ax_flatten),25), histtype='step')
plt.plot(np.linspace(np.min(ax_flatten),np.max(ax_flatten),100), stats.norm.pdf(np.linspace(np.min(ax_flatten),np.max(ax_flatten),100), loc=0, scale=nstd), '--k')
plt.savefig('/home/hunter.gabbard/public_html/Burst/Gauss_pulse_testing/gen_hist_total.png')
plt.close()

