import sys

sys.path.append("../")

import numpy as np
import pandas as pd
import torch
from torch_ctr.models.ranking import WideDeep, DeepFM
from torch_ctr.trainers import CTRTrainer
from torch_ctr.basic.features import DenseFeature, SparseFeature
from torch_ctr.basic.utils import DataGenerator
from tqdm import tqdm
from sklearn.preprocessing import MinMaxScaler, LabelEncoder


def convert_numeric_feature(val):
    v = int(val)
    if v > 2:
        return int(np.log(v)**2)
    else:
        return v - 2


def get_criteo_data_dict(data_path):
    data = pd.read_csv(data_path)
    dense_features = [f for f in data.columns.tolist() if f[0] == "I"]
    sparse_features = [f for f in data.columns.tolist() if f[0] == "C"]

    data[sparse_features] = data[sparse_features].fillna('-996',)
    data[dense_features] = data[dense_features].fillna(0,)

    for feat in tqdm(dense_features):  #discretize dense feature and as new sparse feature
        sparse_features.append(feat + "_cat")
        data[feat + "_cat"] = data[feat].apply(lambda x: convert_numeric_feature(x))

    sca = MinMaxScaler()  #scaler dense feature
    data[dense_features] = sca.fit_transform(data[dense_features])

    for feat in tqdm(sparse_features):  #encode sparse feature
        lbe = LabelEncoder()
        data[feat] = lbe.fit_transform(data[feat])

    dense_feas = [DenseFeature(feature_name) for feature_name in dense_features]
    sparse_feas = [SparseFeature(feature_name, vocab_size=data[feature_name].nunique(), embed_dim=16) for feature_name in sparse_features]
    y = data["label"]
    del data["label"]
    x = data
    return dense_feas, sparse_feas, x, y


def main(dataset_path, model_name, epoch, learning_rate, batch_size, weight_decay, device, save_dir, seed):
    torch.manual_seed(seed)
    dense_feas, sparse_feas, x, y = get_criteo_data_dict(dataset_path)
    dg = DataGenerator(x, y)
    train_dataloader, val_dataloader, test_dataloader = dg.generate_dataloader(split_ratio=[0.8, 0.1], batch_size=batch_size)
    if model_name == "widedeep":
        model = WideDeep(wide_features=dense_feas, deep_features=sparse_feas, mlp_params={"dims": [256, 128], "dropout": 0.2, "activation": "relu"})
    elif model_name == "deepfm":
        model = DeepFM(deep_features=dense_feas, fm_features=sparse_feas, mlp_params={"dims": [256, 128], "dropout": 0.2, "activation": "relu"})

    ctr_trainer = CTRTrainer(model, optimizer_params={"lr": learning_rate, "weight_decay": weight_decay}, n_epoch=epoch, earlystop_patience=4, device=device, model_path=save_dir)
    #scheduler_fn=torch.optim.lr_scheduler.StepLR,scheduler_params={"step_size": 2,"gamma": 0.8},
    ctr_trainer.fit(train_dataloader, val_dataloader)
    auc = ctr_trainer.evaluate(ctr_trainer.model, test_dataloader)
    print(f'test auc: {auc}')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset_path', default="./data/criteo/criteo_sample.csv")
    parser.add_argument('--model_name', default='widedeep')
    parser.add_argument('--epoch', type=int, default=2)  #100
    parser.add_argument('--learning_rate', type=float, default=1e-3)
    parser.add_argument('--batch_size', type=int, default=16)  #4096
    parser.add_argument('--weight_decay', type=float, default=1e-3)
    parser.add_argument('--device', default='cpu')  #cuda:0
    parser.add_argument('--save_dir', default='./')
    parser.add_argument('--seed', type=int, default=2022)

    args = parser.parse_args()
    main(args.dataset_path, args.model_name, args.epoch, args.learning_rate, args.batch_size, args.weight_decay, args.device, args.save_dir, args.seed)
"""
python run_criteo.py --model_name widedeep
python run_criteo.py --model_name deepfm
"""