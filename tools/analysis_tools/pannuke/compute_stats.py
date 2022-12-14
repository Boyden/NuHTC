"""run.

Usage:
  compute_stats.py --true_path=<n> --pred_path=<n> --type_path=<n> --save_path=<n> [--num_classes=<n>]
  compute_stats.py (-h | --help)
  compute_stats.py --version

Options:
  -h --help             Show this string.
  --version             Show version.
  --true_path=<n>    Root path to where the ground-truth is saved.
  --pred_path=<n>    Root path to where the predictions are saved.
  --type_path=<n>    Root path to where the types are saved.
  --save_path=<n>    Path where the prediction CSV files will be saved
  --num_classes=<n>   The number of the classes. [default: 5].
"""


import docopt
import os
import numpy as np
import pandas as pd
from utils import get_fast_pq, remap_label, binarize

tissue_types = [
                'Adrenal_gland',
                'Bile-duct',
                'Bladder',
                'Breast',
                'Cervix',
                'Colon',
                'Esophagus',
                'HeadNeck',
                'Kidney',
                'Liver',
                'Lung',
                'Ovarian',
                'Pancreatic',
                'Prostate',
                'Skin',
                'Stomach',
                'Testis',
                'Thyroid',
                'Uterus'
                ]

def main(args):
    """
    This function returns the statistics reported on the PanNuke dataset, reported in the paper below:

    Gamper, Jevgenij, Navid Alemi Koohbanani, Simon Graham, Mostafa Jahanifar, Syed Ali Khurram,
    Ayesha Azam, Katherine Hewitt, and Nasir Rajpoot.
    "PanNuke Dataset Extension, Insights and Baselines." arXiv preprint arXiv:2003.10778 (2020).

    Args:
    Root path to the ground-truth
    Root path to the predictions
    Path where results will be saved

    Output:
    Terminal output of bPQ and mPQ results for each class and across tissues
    Saved CSV files for bPQ and mPQ results for each class and across tissues
    """

    true_root = args['--true_path']
    pred_root = args['--pred_path']
    save_path = args['--save_path']
    type_path = args['--type_path']
    num_classes = int(args['--num_classes'])

    if not os.path.exists(save_path):
        os.mkdir(save_path)

    if os.path.splitext(true_root)[1] != '':
        true_path = true_root
        true_root = os.path.dirname(true_root)
    else:
        true_path = os.path.join(true_root,'masks.npy')  # path to the GT for a specific split

    if os.path.splitext(pred_root)[1] != '':
        pred_path = pred_root
    else:
        pred_path = os.path.join(pred_root, 'masks.npy')  # path to the predictions for a specific split

    if os.path.splitext(type_path)[1] == '':
        type_path = os.path.join(type_path,'types.npy') # path to the nuclei types

    # load the data
    true = np.load(true_path)
    pred = np.load(pred_path)
    types = np.load(type_path)

    mPQ_all = []
    bPQ_all = []

    # loop over the images
    for i in range(true.shape[0]):
        pq = []
        pred_bin = binarize(pred[i,:,:,:num_classes])
        pred_bin = remap_label(pred_bin)
        true_bin = binarize(true[i,:,:,:num_classes])

        if len(np.unique(true_bin)) == 1:
            pq_bin = np.nan # if ground truth is empty for that class, skip from calculation
        else:
            [_, _, pq_bin], _ = get_fast_pq(true_bin, pred_bin) # compute PQ

        # loop over the classes
        for j in range(num_classes):
            pred_tmp = pred[i,:,:,j]
            pred_tmp = pred_tmp.astype('int32')
            true_tmp = true[i,:,:,j]
            true_tmp = true_tmp.astype('int32')
            pred_tmp = remap_label(pred_tmp)
            true_tmp = remap_label(true_tmp)

            if len(np.unique(true_tmp)) == 1:
                pq_tmp = np.nan # if ground truth is empty for that class, skip from calculation
            else:
                [_, _, pq_tmp] , _ = get_fast_pq(true_tmp, pred_tmp) # compute PQ

            pq.append(pq_tmp)

        mPQ_all.append(pq)
        bPQ_all.append([pq_bin])

    # using np.nanmean skips values with nan from the mean calculation
    mPQ_each_image = [np.nanmean(pq) for pq in mPQ_all]
    bPQ_each_image = [np.nanmean(pq_bin) for pq_bin in bPQ_all]

    # class metric
    neo_PQ = np.nanmean([pq[0] for pq in mPQ_all])
    inflam_PQ = np.nanmean([pq[1] for pq in mPQ_all])
    conn_PQ = np.nanmean([pq[2] for pq in mPQ_all])
    dead_PQ = np.nanmean([pq[3] for pq in mPQ_all])
    nonneo_PQ = np.nanmean([pq[4] for pq in mPQ_all])

    # Print for each class
    print('Printing calculated metrics on a single split')
    print('-'*40)
    print('Neoplastic PQ: {}'.format(neo_PQ))
    print('Inflammatory PQ: {}'.format(inflam_PQ))
    print('Connective PQ: {}'.format(conn_PQ))
    print('Dead PQ: {}'.format(dead_PQ))
    print('Non-Neoplastic PQ: {}'.format(nonneo_PQ))
    print('-' * 40)

    # Save per-class metrics as a csv file
    for_dataframe = {'Class Name': ['Neoplastic', 'Inflam', 'Connective', 'Dead', 'Non-Neoplastic'],
                        'PQ': [neo_PQ, inflam_PQ, conn_PQ, dead_PQ, nonneo_PQ]}
    df = pd.DataFrame(for_dataframe, columns=['Class Name', 'PQ'])
    df.to_csv(save_path + '/class_stats.csv')

    # Print for each tissue
    all_tissue_mPQ = []
    all_tissue_bPQ = []
    for tissue_name in tissue_types:
        indices = [i for i, x in enumerate(types) if x == tissue_name]
        tissue_PQ = [mPQ_each_image[i] for i in indices]
        print('{} PQ: {} '.format(tissue_name, np.nanmean(tissue_PQ)))
        tissue_PQ_bin = [bPQ_each_image[i] for i in indices]
        print('{} PQ binary: {} '.format(tissue_name, np.nanmean(tissue_PQ_bin)))
        all_tissue_mPQ.append(np.nanmean(tissue_PQ))
        all_tissue_bPQ.append(np.nanmean(tissue_PQ_bin))

    # Save per-tissue metrics as a csv file
    for_dataframe = {'Tissue name': tissue_types + ['mean'],
                        'PQ': all_tissue_mPQ + [np.nanmean(all_tissue_mPQ)] , 'PQ bin': all_tissue_bPQ + [np.nanmean(all_tissue_bPQ)]}
    df = pd.DataFrame(for_dataframe, columns=['Tissue name', 'PQ', 'PQ bin'])
    df.to_csv(save_path + '/tissue_stats.csv')

    # Show overall metrics - mPQ is average PQ over the classes and the tissues, bPQ is average binary PQ over the tissues
    print('-' * 40)
    print('Average mPQ:{}'.format(np.nanmean(all_tissue_mPQ)))
    print('Average bPQ:{}'.format(np.nanmean(all_tissue_bPQ)))

#####
if __name__ == '__main__':
    args = docopt.docopt(__doc__, version='PanNuke Evaluation v1.0')
    main(args)
