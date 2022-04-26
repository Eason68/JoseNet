from model import PointMLP
from dataLoader import S3DISDataset
import torch
import os
from datetime import datetime
from tqdm import tqdm
import numpy as np
from sklearn.metrics import confusion_matrix
import torch.nn.functional as F
import argparse

def stats_overall_accuracy(cm):
    """
    Compute the overall accuracy.
    """
    return np.trace(cm)/cm.sum()


def stats_pfa_per_class(cm):
    """
    Compute the probability of false alarms.
    """
    sums = np.sum(cm, axis=0)
    mask = (sums > 0)
    sums[sums == 0] = 1
    pfa_per_class = (cm.sum(axis=0)-np.diag(cm)) / sums
    pfa_per_class[np.logical_not(mask)] = -1
    average_pfa = pfa_per_class[mask].mean()
    return average_pfa, pfa_per_class


def stats_accuracy_per_class(cm):
    """
    Compute the accuracy per class and average
    puts -1 for invalid values (division per 0)
    returns average accuracy, accuracy per class
    """
    # equvalent to for class i to
    # number or true positive of class i (data[target==i]==i).sum()/ number of elements of i (target==i).sum()
    sums = np.sum(cm, axis=1)
    mask = (sums>0)
    sums[sums == 0] = 1
    accuracy_per_class = np.diag(cm) / sums #sum over lines
    accuracy_per_class[np.logical_not(mask)] = -1
    average_accuracy = accuracy_per_class[mask].mean()
    return average_accuracy, accuracy_per_class


def stats_iou_per_class(cm, ignore_missing_classes=True):
    """
    Compute the iou per class and average iou
    Puts -1 for invalid values
    returns average iou, iou per class
    """

    sums = (np.sum(cm, axis=1) + np.sum(cm, axis=0) - np.diag(cm))
    mask = (sums>0)
    sums[sums == 0] = 1
    iou_per_class = np.diag(cm) / sums
    iou_per_class[np.logical_not(mask)] = -1

    if mask.sum()>0:
        average_iou = iou_per_class[mask].mean()
    else:
        average_iou = 0

    return average_iou, iou_per_class


def stats_f1score_per_class(cm):
    """
    Compute f1 scores per class and mean f1.
    puts -1 for invalid classes
    returns average f1 score, f1 score per class
    """
    # defined as 2 * recall * prec / recall + prec
    sums = (np.sum(cm, axis=1) + np.sum(cm, axis=0))
    mask = (sums > 0)
    sums[sums == 0] = 1
    f1score_per_class = 2 * np.diag(cm) / sums
    f1score_per_class[np.logical_not(mask)] = -1
    average_f1_score = f1score_per_class[mask].mean()
    return average_f1_score, f1score_per_class


def train(args):

    # create the network
    print("Creating network...")
    net = PointMLP()
    net.cuda()
    net = torch.nn.DataParallel(net)
    if args.pretrain:
        net.load_state_dict(torch.load(os.path.join(args.save_dir, "pretrain.pth")))

    # print("parameters", count_parameters(net))

    print("Creating dataloader and optimizer...")
    train_data = S3DISDataset(split="train", data_folder=args.data_path, test_area=args.test_area,
                              num_points=args.num_points, block_size=args.block_size, transform=args.transform)
    train_loader = torch.utils.data.DataLoader(train_data, batch_size=args.batch_size, shuffle=True, num_workers=args.threads)

    test_data = S3DISDataset(split="test", data_folder=args.data_path, test_area=args.test_area,
                             num_points=args.num_points, block_size=args.block_size, transform=args.transform)
    test_loader = torch.utils.data.DataLoader(test_data, batch_size=args.batch_size, shuffle=False, num_workers=args.threads)

    optimizer = torch.optim.Adam(net.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=20, gamma=0.8)
    print("done")

    # create the root folder
    print("Creating results folder")
    time_string = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    root_folder = os.path.join(args.save_dir, "{}_area{}_{}_{}".format(args.model, args.test_area, args.num_points, time_string))
    os.makedirs(root_folder, exist_ok=True)
    print("done at", root_folder)

    # create the log file
    logs = open(os.path.join(root_folder, "log.txt"), "w")
    maxIOU = 0.0

    # iterate over epochs
    for epoch in range(args.epochs):

        # training
        net.train()

        lr = optimizer.param_groups[0]['lr']
        print('LearningRate:', lr)
        for param_group in optimizer.param_groups:
            param_group['lr'] = lr

        train_loss = 0
        cm = np.zeros((args.num_classes, args.num_classes))
        t = tqdm(train_loader, ncols=100, desc="Train {}".format(epoch))
        for points, labels in t:

            points = points.permute(0, 2, 1)
            points = points.cuda()
            labels = labels.cuda()

            optimizer.zero_grad()

            outputs = net(points)

            loss = F.cross_entropy(outputs.contiguous().view(-1, args.num_classes), labels.contiguous().view(-1))
            loss.backward()
            optimizer.step()
            scheduler.step()

            output_np = np.argmax(outputs.cpu().detach().numpy(), axis=2).copy()
            target_np = labels.cpu().numpy().copy()

            cm_ = confusion_matrix(target_np.ravel(), output_np.ravel(), labels=list(range(args.num_classes)))
            cm += cm_

            oa = f"{stats_overall_accuracy(cm):.3f}"
            aa = f"{stats_accuracy_per_class(cm)[0]:.3f}"
            iou = f"{stats_iou_per_class(cm)[0]:.3f}"

            train_loss += loss.detach().cpu().item()

            t.set_postfix(OA=oa, IOU=iou, LOSS=f"{train_loss / cm.sum():.3e}")

        # validation
        net.eval()
        cm_test = np.zeros((args.num_classes, args.num_classes))
        test_loss = 0

        t = tqdm(test_loader, ncols=100, desc="Test {}".format(epoch))

        with torch.no_grad():
            for points, labels in t:

                points = points.permute(0, 2, 1)
                points = points.cuda()
                labels = labels.cuda()

                outputs = net(points)
                loss = F.cross_entropy(outputs.contiguous().view(-1, args.num_classes), labels.contiguous().view(-1))

                output_np = np.argmax(outputs.cpu().detach().numpy(), axis=2).copy()
                target_np = labels.cpu().numpy().copy()

                cm_ = confusion_matrix(target_np.ravel(), output_np.ravel(), labels=list(range(args.num_classes)))
                cm_test += cm_

                oa_val = f"{stats_overall_accuracy(cm_test):.3f}"
                aa_val = f"{stats_accuracy_per_class(cm_test)[0]:.3f}"
                iou_val = f"{stats_iou_per_class(cm_test)[0]:.3f}"

                test_loss += loss.detach().cpu().item()

                t.set_postfix(OA=oa_val, IOU=iou_val, LOSS=f"{test_loss / cm_test.sum():.3e}")

        # save the model
        torch.save(net.state_dict(), os.path.join(root_folder, "state_dict.pth"))
        if maxIOU < float(iou_val):
            # save the model
            torch.save(net.state_dict(), os.path.join(root_folder, "state_dict" + str(iou_val) + ".pth"))
            maxIOU = float(iou_val)
        # write the logs
        logs.write(f"{epoch} {oa} {aa} {iou} {oa_val} {aa_val} {iou_val}\n")
        logs.flush()

    logs.close()


def test(args):

    # create the network
    print("Creating network...")
    net = PointMLP()
    net.cuda()
    net = torch.nn.DataParallel(net)

    net.load_state_dict(torch.load(os.path.join(args.save_dir, "state_dict.pth")))
    # net.cuda()
    net.eval()

    # TODO: test the model
    pass



def main():
    parser = argparse.ArgumentParser()
    # parser.add_argument("--test", action="store_true")
    # parser.add_argument("--ply", action="store_true", help="save ply files (test mode)")
    parser.add_argument("--save_dir", default="results/", type=str)
    parser.add_argument("--data_path", default='s3dis_data', type=str)
    parser.add_argument("--batch_size", "-b", default=2, type=int)
    parser.add_argument("--num_points", default=4096, type=int)
    parser.add_argument("--test_area", default=5, type=int)
    parser.add_argument("--block_size", default=1.0, type=float)
    # parser.add_argument("--iter", default=1000, type=int)
    parser.add_argument("--threads", default=1, type=int)
    # parser.add_argument("--npick", default=16, type=int)
    # parser.add_argument("--savepts", action="store_true")
    # parser.add_argument("--nocolor", action="store_true")
    parser.add_argument("--pretrain", default=False, type=bool)
    parser.add_argument("--lr", default=0.0001, type=float)
    # parser.add_argument("--test_step", default=0.2, type=float)
    parser.add_argument("--epochs", default=350, type=int)
    # parser.add_argument("--jitter", default=0.4, type=float)
    parser.add_argument("--model", default="PointMLP", type=str)
    # parser.add_argument("--drop", default=0, type=float)
    parser.add_argument("--num_classes", default=13, type=int)
    parser.add_argument("--transform", default=False, type=bool)
    args = parser.parse_args()


    train(args)
    test(args)


if __name__ == '__main__':
    main()