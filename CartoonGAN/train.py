import sys
sys.path.append("pytorch-CartoonGAN")
import os, time, pickle, argparse, networks, utils
import torch
import torch.nn as nn
import torch.optim as optim
import matplotlib.pyplot as plt
from torchvision import transforms
from tqdm import tqdm
from edge_promoting import edge_promoting


# Parse Arguments
parser = argparse.ArgumentParser()
parser.add_argument('--name', required=False, default='CartoonGan_Converter',  help='')
parser.add_argument('--src_data', required=False, default='data/src_data',  help='sec data path')
parser.add_argument('--tgt_data', required=False, default='data/tgt_data',  help='tgt data path')
parser.add_argument('--vgg_model', required=False, default='vgg19.pth', help='pre-trained VGG19 model path')
parser.add_argument('--in_g_channel', type=int, default=3, help='input channel for generator')
parser.add_argument('--out_g_channel', type=int, default=3, help='output channel for generator')
parser.add_argument('--in_d_channel', type=int, default=3, help='input channel for discriminator')
parser.add_argument('--out_d_channel', type=int, default=1, help='output channel for discriminator')
parser.add_argument('--batch_size', type=int, default=8, help='batch size')
parser.add_argument('--generator_features', type=int, default=64)
parser.add_argument('--discriminator_features', type=int, default=32)
parser.add_argument('--resnet_block', type=int, default=8, help='the number of resnet block layer for generator')
parser.add_argument('--input_size', type=int, default=256, help='input size')
parser.add_argument('--train_epoch', type=int, default=100)
parser.add_argument('--pre_train_epoch', type=int, default=10)
parser.add_argument('--lrD', type=float, default=0.0002, help='learning rate, default=0.0002')
parser.add_argument('--lrG', type=float, default=0.0002, help='learning rate, default=0.0002')
parser.add_argument('--con_lambda', type=float, default=10, help='lambda for content loss')
parser.add_argument('--beta1', type=float, default=0.5, help='beta1 for Adam optimizer')
parser.add_argument('--beta2', type=float, default=0.999, help='beta2 for Adam optimizer')
parser.add_argument('--latest_generator_model', required=False, default='CartoonGan_Converter_results/generator_latest.pkl', help='the latest trained model path')
parser.add_argument('--latest_discriminator_model', required=False, default='CartoonGan_Converter_results/discriminator_latest.pkl', help='the latest trained model path')
args = parser.parse_args()

#device
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# results save path
if not os.path.isdir(os.path.join(args.name + '_results', 'Reconstruction')):
    os.makedirs(os.path.join(args.name + '_results', 'Reconstruction'))
if not os.path.isdir(os.path.join(args.name + '_results', 'Transfer')):
    os.makedirs(os.path.join(args.name + '_results', 'Transfer'))

# edge-promoting
if not os.path.isdir(os.path.join(args.tgt_data, 'pair')) or not os.listdir(os.path.join(args.tgt_data, 'pair')):
    print('edge-promoting start!!')
    edge_promoting(os.path.join(args.tgt_data, 'train'), os.path.join(args.tgt_data, 'pair'))
else:
    print('edge-promoting already done')

#load data

src_transform = transforms.Compose([
        transforms.Resize((args.input_size, args.input_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5))
])
tgt_transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5))
])
train_loader_src = utils.data_load(os.path.join(args.src_data), 'train', src_transform, args.batch_size, shuffle=True, drop_last=True)
train_loader_tgt = utils.data_load(os.path.join(args.tgt_data), 'pair', tgt_transform, args.batch_size, shuffle=True, drop_last=True)
test_loader_src = utils.data_load(os.path.join(args.src_data), 'test', src_transform, 1, shuffle=True, drop_last=True)

#network 

G = networks.generator(args.in_g_channel, args.out_g_channel, args.generator_features, args.batch_size)
if args.latest_generator_model != '':
    if torch.cuda.is_available():
        G.load_state_dict(torch.load(args.latest_generator_model))
    else:
        # cpu mode
        G.load_state_dict(torch.load(args.latest_generator_model, map_location=lambda storage, loc: storage))

D = networks.discriminator(args.in_d_channel, args.out_d_channel, args.discriminator_features)
if args.latest_discriminator_model != '':
    if torch.cuda.is_available():
        D.load_state_dict(torch.load(args.latest_discriminator_model))
    else:
        D.load_state_dict(torch.load(args.latest_discriminator_model, map_location=lambda storage, loc: storage))
VGG = networks.VGG19(init_weights=args.vgg_model, feature_mode=True)
G.to(device)
D.to(device)
VGG.to(device)
G.train()
D.train()
VGG.eval()
print('---------- Networks initialized -------------')
utils.print_network(G)
utils.print_network(D)
utils.print_network(VGG)
print('-----------------------------------------------')

# loss function
BCE_loss = nn.BCELoss().to(device)
L1_loss = nn.L1Loss().to(device)

#adam optimizer
G_optimizer = optim.Adam(G.parameters(), lr=args.lrG, betas=(args.beta1, args.beta2))
D_optimizer = optim.Adam(D.parameters(), lr=args.lrD, betas=(args.beta1, args.beta2))
G_scheduler = optim.lr_scheduler.MultiStepLR(optimizer=G_optimizer, milestones=[args.train_epoch // 2, args.train_epoch // 4 * 3], gamma=0.1)
D_scheduler = optim.lr_scheduler.MultiStepLR(optimizer=D_optimizer, milestones=[args.train_epoch // 2, args.train_epoch // 4 * 3], gamma=0.1)

pre_train_hist = {}
pre_train_hist['Recon_loss'] = []
pre_train_hist['per_epoch_time'] = []
pre_train_hist['total_time'] = []

# pre-train
if args.latest_generator_model == '':
    print('Pre-training start!')
    start_time = time.time()
    for epoch in tqdm(range(args.pre_train_epoch)):
        epoch_start_time = time.time()
        Recon_losses = []
        for x, _ in train_loader_src:
            x = x.to(device)

            # train generator G
            G_optimizer.zero_grad()

            x_feature = VGG((x + 1) / 2)
            G_ = G(x)
            G_feature = VGG((G_ + 1) / 2)

            Recon_loss = 10 * L1_loss(G_feature, x_feature.detach())
            Recon_losses.append(Recon_loss.item())
            pre_train_hist['Recon_loss'].append(Recon_loss.item())

            Recon_loss.backward()
            G_optimizer.step()

        per_epoch_time = time.time() - epoch_start_time
        pre_train_hist['per_epoch_time'].append(per_epoch_time)
        print('[%d/%d] - time: %.2f, Recon loss: %.3f' % ((epoch + 1), args.pre_train_epoch, per_epoch_time, torch.mean(torch.FloatTensor(Recon_losses))))

    total_time = time.time() - start_time
    pre_train_hist['total_time'].append(total_time)
    with open(os.path.join(args.name + '_results',  'pre_train_hist.pkl'), 'wb') as f:
        pickle.dump(pre_train_hist, f)

    with torch.no_grad():
        G.eval()
        for n, (x, _) in enumerate(train_loader_src):
            x = x.to(device)
            G_recon = G(x)
            result = torch.cat((x[0], G_recon[0]), 2)
            path = os.path.join(args.name + '_results', 'Reconstruction', args.name + '_train_recon_' + str(n + 1) + '.png')
            plt.imsave(path, (result.cpu().numpy().transpose(1, 2, 0) + 1) / 2)
            if n == 4:
                break

        for n, (x, _) in enumerate(test_loader_src):
            x = x.to(device)
            G_recon = G(x)
            result = torch.cat((x[0], G_recon[0]), 2)
            path = os.path.join(args.name + '_results', 'Reconstruction', args.name + '_test_recon_' + str(n + 1) + '.png')
            plt.imsave(path, (result.cpu().numpy().transpose(1, 2, 0) + 1) / 2)
            if n == 4:
                break
else:
    print('Load the latest generator model, no need to pre-train')


train_hist = {}
train_hist['Disc_loss'] = []
train_hist['Gen_loss'] = []
train_hist['Con_loss'] = []
train_hist['per_epoch_time'] = []
train_hist['total_time'] = []


# training

print('training start!')
start_time = time.time()
real = torch.ones(args.batch_size, 1, args.input_size // 4, args.input_size // 4).to(device)
fake = torch.zeros(args.batch_size, 1, args.input_size // 4, args.input_size // 4).to(device)
for epoch in tqdm(range(args.train_epoch)):
    epoch_start_time = time.time()
    G.train()
    #G_scheduler.step()
    #D_scheduler.step()
    Disc_losses = []
    Gen_losses = []
    Con_losses = []
    for (x, _), (y, _) in zip(train_loader_src, train_loader_tgt):
        e = y[:, :, :, args.input_size:]
        y = y[:, :, :, :args.input_size]
        x, y, e = x.to(device), y.to(device), e.to(device)

        # train D
        D_optimizer.zero_grad()

        D_real = D(y)
        D_real_loss = BCE_loss(D_real, real)

        G_ = G(x)
        D_fake = D(G_)
        D_fake_loss = BCE_loss(D_fake, fake)

        D_edge = D(e)
        D_edge_loss = BCE_loss(D_edge, fake)

        Disc_loss = D_real_loss + D_fake_loss + D_edge_loss
        Disc_losses.append(Disc_loss.item())
        train_hist['Disc_loss'].append(Disc_loss.item())

        Disc_loss.backward()
        D_optimizer.step()

        # train G
        G_optimizer.zero_grad()

        G_ = G(x)
        D_fake = D(G_)
        D_fake_loss = BCE_loss(D_fake, real)

        x_feature = VGG((x + 1) / 2)
        G_feature = VGG((G_ + 1) / 2)
        Con_loss = args.con_lambda * L1_loss(G_feature, x_feature.detach())

        Gen_loss = D_fake_loss + Con_loss
        Gen_losses.append(D_fake_loss.item())
        train_hist['Gen_loss'].append(D_fake_loss.item())
        Con_losses.append(Con_loss.item())
        train_hist['Con_loss'].append(Con_loss.item())

        Gen_loss.backward()
        G_optimizer.step()
    G_scheduler.step()
    D_scheduler.step()

    per_epoch_time = time.time() - epoch_start_time
    train_hist['per_epoch_time'].append(per_epoch_time)
    print(
    '[%d/%d] - time: %.2f, Disc loss: %.3f, Gen loss: %.3f, Con loss: %.3f' % ((epoch + 1), args.train_epoch, per_epoch_time, torch.mean(torch.FloatTensor(Disc_losses)),
        torch.mean(torch.FloatTensor(Gen_losses)), torch.mean(torch.FloatTensor(Con_losses))))

    if epoch % 2 == 1 or epoch == args.train_epoch - 1:
        with torch.no_grad():
            G.eval()
            for n, (x, _) in enumerate(train_loader_src):
                x = x.to(device)
                G_recon = G(x)
                result = torch.cat((x[0], G_recon[0]), 2)
                path = os.path.join(args.name + '_results', 'Transfer', str(epoch+1) + '_epoch_' + args.name + '_train_' + str(n + 1) + '.png')
                plt.imsave(path, (result.cpu().numpy().transpose(1, 2, 0) + 1) / 2)
                if n == 4:
                    break

            for n, (x, _) in enumerate(test_loader_src):
                x = x.to(device)
                G_recon = G(x)
                result = torch.cat((x[0], G_recon[0]), 2)
                path = os.path.join(args.name + '_results', 'Transfer', str(epoch+1) + '_epoch_' + args.name + '_test_' + str(n + 1) + '.png')
                plt.imsave(path, (result.cpu().numpy().transpose(1, 2, 0) + 1) / 2)
                if n == 4:
                    break

            torch.save(G.state_dict(), os.path.join(args.name + '_results', 'generator_latest.pkl'))
            torch.save(D.state_dict(), os.path.join(args.name + '_results', 'discriminator_latest.pkl'))

total_time = time.time() - start_time
train_hist['total_time'].append(total_time)

print("Avg one epoch time: %.2f, total %d epochs time: %.2f" % (torch.mean(torch.FloatTensor(train_hist['per_epoch_time'])), args.train_epoch, total_time))
print("Training finish!... save training results")

torch.save(G.state_dict(), os.path.join(args.name + '_results',  'generator_param.pkl'))
torch.save(D.state_dict(), os.path.join(args.name + '_results',  'discriminator_param.pkl'))
with open(os.path.join(args.name + '_results',  'train_hist.pkl'), 'wb') as f:
    pickle.dump(train_hist, f)
