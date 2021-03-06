import numpy as np
import torch
from utils import knn_point, index_points


class Metrics():
    def __init__(self):
        pass

    @staticmethod
    def stats_overall_accuracy(cm):
        """
        Compute the overall accuracy.
        """
        return np.trace(cm) / cm.sum()

    @staticmethod
    def stats_pfa_per_class(cm):
        """
        Compute the probability of false alarms.
        """
        sums = np.sum(cm, axis=0)
        mask = (sums > 0)
        sums[sums == 0] = 1
        pfa_per_class = (cm.sum(axis=0) - np.diag(cm)) / sums
        pfa_per_class[np.logical_not(mask)] = -1
        average_pfa = pfa_per_class[mask].mean()
        return average_pfa, pfa_per_class

    @staticmethod
    def stats_accuracy_per_class(cm):
        """
        Compute the accuracy per class and average
        puts -1 for invalid values (division per 0)
        returns average accuracy, accuracy per class
        """
        # equvalent to for class i to
        # number or true positive of class i (data[target==i]==i).sum()/ number of elements of i (target==i).sum()
        sums = np.sum(cm, axis=1)
        mask = (sums > 0)
        sums[sums == 0] = 1
        accuracy_per_class = np.diag(cm) / sums  # sum over lines
        accuracy_per_class[np.logical_not(mask)] = -1
        average_accuracy = accuracy_per_class[mask].mean()
        return average_accuracy, accuracy_per_class

    @staticmethod
    def stats_iou_per_class(cm):
        """
        Compute the iou per class and average iou
        Puts -1 for invalid values
        returns average iou, iou per class
        """

        sums = (np.sum(cm, axis=1) + np.sum(cm, axis=0) - np.diag(cm))
        mask = (sums > 0)
        sums[sums == 0] = 1
        iou_per_class = np.diag(cm) / sums
        iou_per_class[np.logical_not(mask)] = -1

        if mask.sum() > 0:
            average_iou = iou_per_class[mask].mean()
        else:
            average_iou = 0

        return average_iou, iou_per_class

    @staticmethod
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

    @staticmethod
    def stats_boundary_iou(coords, labels, output):
        """
        Compute the IoU at the boundary
        :param coords: coordinates of the original point
        :param labels: labels of the original point
        :param output: the final output of the model, i.e. the labels of the predicted points
        :return: the IoU at the boundary: boundary_IoU
        """
        kneighbor = 32
        coords = coords.permute(0, 2, 1)[..., :3]
        neighbor_indexs = knn_point(kneighbor, coords, coords)  # [B, N, K]

        # Groundtruth
        labels = labels.unsqueeze(dim=-1)  # [B, N]->[B, N, 1]
        neighbor_labels = index_points(labels, neighbor_indexs).squeeze()  # [B, N, 1]->[B, N, K, 1]->[B, N, K]
        mask_labels = labels == neighbor_labels  # [B, N, K], bool
        mask_labels = torch.sum(mask_labels.int(), dim=-1)  # [B, N]
        true_boundary = (mask_labels > 0) & (mask_labels < kneighbor)  # [B, N], bool

        # Prediction
        output = torch.argmax(output, dim=-1).unsqueeze(dim=-1)  # [B, N, 13]->[B, N]->[B, N, 1]
        neighbor_output = index_points(output, neighbor_indexs).squeeze()
        mask_output = output == neighbor_output
        mask_output = torch.sum(mask_output.int(), dim=-1)
        pred_boundary = (mask_output > 0) & (mask_output < kneighbor)

        # Calculate the boundary IoU
        boundary_I = true_boundary & pred_boundary
        boundary_U = true_boundary | pred_boundary
        boundary_IoU = torch.sum(boundary_I.int()).float() / (torch.sum(boundary_U.int()).float() + 1e-6)

        return boundary_IoU
