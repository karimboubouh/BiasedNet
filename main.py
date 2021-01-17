import os
import copy
import time
from pprint import pprint
import numpy as np
import torch

from src.datasets import get_dataset
from src.models import initialize_models
from src.network import random_graph, network_graph
from src.learners import average, model_propagation, avgrad
from src.plots import plot_train_history
from src.utils import exp_details, set_device, log, load_conf

if __name__ == '__main__':
    np.random.seed(0)
    torch.set_num_threads(1)
    start_time = time.time()
    # load experiment configuration from CLI arguments
    args = load_conf()
    args.iid = 0
    args.batch_size = 256
    args.unequal = 0
    args.num_users = 20
    args.epochs = 3
    args.test_scope = "neighborhood"

    args.rounds = 500
    # print experiment details
    exp_details(args)
    # set device
    device = set_device(args)
    # load dataset and initialize user groups
    train_ds, test_ds, user_groups = get_dataset(args)
    # build users models
    models = initialize_models(args, same=False, device=device)
    # setup the network topology
    topology = random_graph(models, sigma=-0.7)
    # build the network graph
    graph = network_graph(topology, models, train_ds, test_ds, user_groups, args)
    graph.show_similarity()
    # graph.show_neighbors()

    # perform local training
    train_logs = graph.local_training(device)

    # plot the history of local training phase
    # info = {'xlabel': "Epochs", 'title': "Accuracy. vs. No. of epochs"}
    # plot_train_history(train_logs, metric='accuracy', measure="mean", info=info)

    # start collaborative training
    collab_logs = graph.collaborative_training(learner=avgrad, device=device)

    # for peer in graph.peers:
    #     print(peer, peer.model.evaluate(peer.inference, device))

    # plot the history of collaborative training phase
    info = {'xlabel': "Rounds", 'title': "Accuracy. vs. No. of rounds"}
    plot_train_history(collab_logs, metric='accuracy', measure="mean")

    # todo add title attributes
    # plot_train_history(collab_logs, metric='accuracy', measure="max")
    # visualization and figures

    # print(f'Graph contains {len(graph)} nodes.')
