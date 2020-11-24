import pandas as pd
import numpy as np 
import networkx as nx

PATH_TP_NETWORK = './data/tp_network.pkl'
PATH_TEMPORAL_OVERVIEW = './data/temporal_overview.ftr'
PATH_AP_TXN = './data/ap_txn.ftr'
PATH_INVOICE = './data/invoice.ftr'
PATH_INVESTOR = './data/investor.ftr'
PATH_TAXPAYER = './data/taxpayer.ftr'
PATH_FINANCE = './data/finance.ftr'

class Model:
    def __init__(self):
        # initialize taxpayer network
        self.tp_network = nx.read_gpickle(PATH_TP_NETWORK)

        # initialize temporal overview
        self.temporal_overview = pd.read_feather(PATH_TEMPORAL_OVERVIEW)
        self.temporal_overview['date'] = self.temporal_overview['date'].dt.strftime("%Y-%m-%d")

        # load supplementary data for model
        self.ap_txn = pd.read_feather(PATH_AP_TXN)
        self.invoice = pd.read_feather(PATH_INVOICE)
        self.investor = pd.read_feather(PATH_INVESTOR)
        self.taxpayer = pd.read_feather(PATH_TAXPAYER)
        self.finance = pd.read_feather(PATH_FINANCE)

        # declare class variables
        self.ap_list = []
        self.ap_network = None
        self.ap_txn_period = pd.DataFrame()
        self.finance_period = pd.DataFrame()

        # initialize
        self.get_tp_network()

    def get_temporal_overview(self):
        """
        Get the temporal data of ap_transaction_amount to draw the time slider.
        Notice that the data used here is independent to the model output,
        for the sake of having consistent visualization.
        :return:    date: A list of time
                    ap_txn_amount: A list of affiliated party transaction amount by day
        """
        return {
            'date': list(self.temporal_overview['date']),
            'ap_txn_amount': list(self.temporal_overview['txn_sum'])
        }

    def get_tp_network(self, _start_time='2014-01-01', _end_time='2014-12-31', max_txn_length=3, max_control_length=2):
        """
        Remove affiliated parties who have affiliated transactions taken place exceeding a step limit
        :param max_txn_length: maximum steps for a transaction to be considered affiliated
        :param max_control_length: maximum steps for a taxpayer to be considered related to the suspect
        :param _start_time: the start time of query
        :param _end_time: the end time of query
        :return: the resulted TPIIN and a corresponding affiliated transaction network
        """
        # initialize taxpayer network
        self.tp_network = nx.read_gpickle(PATH_TP_NETWORK)  # loading pickle is about 4 times faster than deep copy
        tp_network_undirected = self.tp_network.to_undirected(as_view=True)

        # build the trade network with invoice data
        self.ap_network = nx.DiGraph()
        self.ap_txn_period = self.ap_txn.query('@_start_time <= date <= @_end_time')
        # validate edges by requiring buyer to reach seller within an arbitrary steps in the TPIIN
        for src, tar in zip(self.ap_txn_period['buyer_id'], self.ap_txn_period['seller_id']):
            if nx.shortest_path_length(tp_network_undirected, src, tar) <= max_txn_length:
                self.ap_network.add_edge(src, tar)
        # remove isolated nodes
        self.ap_network.remove_nodes_from(list(nx.isolates(self.ap_network)))

        # create a mapping for affiliated parties
        ap_df = [(i, _ap) for i, ap in enumerate(nx.connected_components(tp_network_undirected)) for _ap in ap]
        ap_df = pd.DataFrame(ap_df, columns=['ap_id', 'tp_id'])

        # remove affiliated parties that have not appeared in ap_network
        _ap_node = list(self.ap_network.nodes())
        _ap_exist = ap_df.query('tp_id in @_ap_node')['ap_id'].drop_duplicates()
        self.tp_network.remove_nodes_from(ap_df.query('ap_id not in @_ap_exist')['tp_id'])

        # obtain the control chain using BFS
        control_chain = set()
        for node in self.ap_network.nodes():
            control_chain.add(node)
            control_chain |= {v for _, v in
                              nx.bfs_edges(tp_network_undirected, source=node, depth_limit=max_control_length)}
        # remove the nodes that are out of reach
        control_chain = [n for n in self.tp_network.nodes() if n not in control_chain]
        self.tp_network.remove_nodes_from(control_chain)

        # augment the taxpayer network with affiliated transactions
        self.tp_network.add_edges_from(list(self.tp_network.edges()), ap_txn=False)  # initialize
        self.tp_network.add_edges_from(list(self.ap_network.edges()), ap_txn=True)
        # assign an id for each affiliated party
        self.ap_list = sorted(list(nx.connected_components(tp_network_undirected)), key=lambda _ap: len(_ap))
        self.finance_period = self.finance.query('@_start_time <= time_end and time_start <= @_end_time')

    def get_affiliated_party_list(self):
        """
        Get the list for affiliated parties with their id, number of inner transactions and nodes.
        The ap_id is for internal use only because the topology of affiliated parties differ
        based on the TPIIN parameter settings.
        :return: json-ready list of affiliated parties
        """
        tp = pd.DataFrame([(i, _ap) for i, ap in enumerate(self.ap_list) for _ap in ap], columns=['ap_id', 'num_nodes'])
        ap_txn = pd.DataFrame([(u, 1) for u, _ in self.ap_network.edges()], columns=['num_nodes', 'num_ap_txn'])
        ap = tp.merge(ap_txn, how='left').groupby('ap_id').count().reset_index()
        return ap.to_dict('records')

    def get_affiliated_party_topo_list(self):
        """
        Get the topology list for affiliated parties with their id, inner taxpayer, trade links with sum transaction
        amount. The ap_id is for internal use only because the topology of affiliated parties differ based on
        the TPIIN parameter settings.
        :return: json-ready list of affiliated parties
        """
        # get the list of nodes in ap_network
        _ap_list = list(self.ap_network.nodes())
        # give id to each ap
        _ap_df = pd.DataFrame([(i, _ap) for i, ap in enumerate(self.ap_list) for _ap in ap], columns=['ap_id', 'tp_id'])

        # retrieve tax evader records
        tax_evader = [n for n, evader in self.tp_network.nodes(data='tax_evader') if evader]
        
        _tax_evader = _ap_df.query('tp_id in @tax_evader').groupby('ap_id').count().reset_index().rename(
            columns={'tp_id': 'num_evader'})
        # retrieve tax deductible records
        _tax_deducted = self.finance.query('tax_deductible > 0')['tp_id'].drop_duplicates()
        _tax_deducted = _ap_df.query('tp_id in @_tax_deducted').groupby('ap_id').count().reset_index().rename(
            columns={'tp_id': 'num_deducted'})

        # filter nodes that are not performing related party transactions
        _ap_df = _ap_df.query('tp_id in @_ap_list')
        # match seller_id with ap_id
        _ap_df_seller = _ap_df.merge(self.ap_txn_period, left_on='tp_id', right_on='seller_id')[
            ['ap_id', 'seller_id', 'buyer_id', 'txn_sum', 'date', 'effective']
        ]
        # match buyer_id with ap_id
        _ap_df = _ap_df_seller.merge(_ap_df, left_on='buyer_id', right_on='tp_id', suffixes=('', '_b'))
        # matching ap_id of both buyer and seller to confirm related party transaction
        _ap_df = _ap_df.query('ap_id == ap_id_b')[['ap_id', 'seller_id', 'buyer_id', 'txn_sum', 'date', 'effective']]
        _ap_df = _ap_df.rename(columns={'effective': 'num_effective'})
        # prepare for count
        _ap_df['num_ap_txn'] = 1
        # sum the total transaction amount and count
        _ap_df = _ap_df.groupby(['ap_id', 'seller_id', 'buyer_id']).sum().round(0).reset_index()
        # prepare links data
        _ap_df['links'] = list(zip(_ap_df['buyer_id'], _ap_df['seller_id'], _ap_df['txn_sum']))
        _ap_df = _ap_df.groupby('ap_id').agg(
            {'txn_sum': np.sum, 'num_ap_txn': np.sum, 'num_effective': np.sum,
             'links': list, 'seller_id': set, 'buyer_id': set}
        )
        # prepare nodes data
        _ap_df['nodes'] = _ap_df.apply(lambda x: list(x.seller_id.union(x.buyer_id)), axis=1)


        # prepare tax evaders data
        _ap_df = _ap_df[['txn_sum', 'num_ap_txn', 'num_effective', 'nodes', 'links']].reset_index()
        _ap_df = _ap_df.merge(_tax_evader, how='left').merge(_tax_deducted, how='left')
        _ap_df = _ap_df.rename(columns={'txn_sum': 'ap_txn_amount'}).fillna(0)
        # filter noisy data
        _ap_df['num_nodes'] = _ap_df.apply(lambda x: len(x.nodes), axis=1)
        _ap_df = _ap_df.query('ap_txn_amount > 0 & num_nodes < 10 & num_ap_txn < 100')
        # provide maximum information
        _nodes_max = np.max(_ap_df.sort_values('num_effective').tail(50)['num_nodes'])
        # _ap_max = np.max(_ap_df.sort_values('num_effective').tail(50)['ap_txn_amount'])
        # _effective_max = _ap_df.sort_values('num_effective').tail(1)['num_effective']
        # _evader_max = np.max(_ap_df.sort_values('num_effective').tail(50)['num_evader'])

        _ap_avg = np.average(_ap_df.sort_values('num_effective').tail(50)['ap_txn_amount'])
        _effective_avg = np.average(_ap_df.sort_values('num_effective').tail(50)['num_effective'])
        _evader_avg = np.average(_ap_df.sort_values('num_effective').tail(50)['num_evader'])
        _ap_std = np.std(_ap_df.sort_values('num_effective').tail(50)['ap_txn_amount'])
        _effective_std = np.std(_ap_df.sort_values('num_effective').tail(50)['num_effective'])
        _evader_std = np.std(_ap_df.sort_values('num_effective').tail(50)['num_evader'])


        # sort the array in descending order
        _ap_df = _ap_df.sort_values('num_effective').tail(50).to_dict("records")



        # prepare the json file
        ap_json = []
        for _ap in _ap_df:
            # # print(_ap['nodes'])\
            # print('s', list(filter(lambda link: link[1] == _ap['nodes'][0], _ap['links'])))
            # print('tin_amount',  reduce(lambda ac,cur: ac+cur[2], list(filter(lambda link: link[1] == _ap['nodes'][0], _ap['links'])),0))
            
            # print('tout_amount', reduce(lambda ac,cur: ac+cur[2], list(filter(lambda link: link[0] == _ap['nodes'][0], _ap['links'])),0))
            

            ap_json.append({
                'ap_id': _ap['ap_id'],
                # 'affiliatedPartyNumData': {
                #     'num_nodes': int(_ap['num_nodes']),
                #     'num_ap_nodes': len([{'id': node} for node in _ap['nodes']]),
                #     'num_evader': int(_ap['num_evader']),  # Sort 3
                #     'num_deducted': int(_ap['num_deducted']),
                #     'num_effective': int(_ap['num_effective']),  # Sort 2
                #     'max_num_nodes': int(_nodes_max),
                # },
                # 'affiliatedPartyAmountData': {
                #     'num_ap_txn': _ap['num_ap_txn'],
                #     'ap_txn_amount': _ap['ap_txn_amount'],  # Sort 1
                #     'max_amount': _ap_max
                # },
                # x = (x - mu) / sigma
                'ap_txn_amount': int(_ap['ap_txn_amount']),  # Sort 1
                'num_effective': int(_ap['num_effective']),  # Sort 2
                'num_evader': int(_ap['num_evader']),  # Sort 3

                'ap_txn_amount_height': int(((_ap['ap_txn_amount']-_ap_avg)/_ap_std + 1) * 25),  # Height 1
                'num_effective_height': int(((_ap['num_effective']-_effective_avg)/_effective_std + 1) * 25),  # Height 2
                'num_evader_height': int(((_ap['num_evader']-_evader_avg)/_evader_std + 1) * 25),  # Height 3

                'affiliatedPartyTopoData': {
                    'nodes': [
                                {
                                    'id': node, 
                                    'is_evader': node in tax_evader,
                                    'profit_amount': reduce(lambda ac,cur: ac+cur[2], list(filter(lambda link: link[1] == node, _ap['links'])),0) - reduce(lambda ac,cur: ac+cur[2], list(filter(lambda link: link[0] == node, _ap['links'])),0)
                                } for node in _ap['nodes']],
                    'links': [{'source': buyer_id, 'target': seller_id, 'ap_txn_amount': txn_sum} for
                              buyer_id, seller_id, txn_sum in _ap['links']],
                }
            })

        return ap_json

    def get_ap_id(self, tp_id):
        """
        Retrieve the corresponding ap_id with tp_id
        :param tp_id: the taxpayer id
        :return: ap_id
        """
        ap_id = -1
        for i, ap in enumerate(self.ap_list, 0):
            if tp_id in ap:
                ap_id = i
                break
        return ap_id

    def get_taxpayer_detail(self, ap_graph):
        tp_list = [n for n, tp in list(ap_graph.nodes(data='tp')) if tp]
        tp_df = self.taxpayer.query('tp_id in @tp_list').set_index('tp_id', drop=True)
        for n in tp_list:
            ap_graph.add_node(n, **dict(tp_df.loc[n]))
        return tp_list

    def get_investor_detail(self, ap_graph):
        in_list = [n for n, inv in list(ap_graph.nodes(data='in')) if inv]
        in_df = self.investor.query('in_id in @in_list').set_index('in_id', drop=True)
        for n in in_list:
            ap_graph.add_node(n, **dict(in_df.loc[n]))
        return in_list

    def get_detail_by_tp_id(self, tp_id):
        """
        Prepare the affiliated party sub-graph with additional node information
        :param tp_id: the requested taxpayer id
        :return: the sub-graph json
        """
        # extract the requested sub-graph
        ap_id = self.get_ap_id(tp_id)
        return self.get_detail_by_ap_id(ap_id) if ap_id != -1 else '{}'

    def get_detail_by_ap_id(self, ap_id):
        """
        Prepare the affiliated party sub-graph with additional node information
        :param ap_id: the requested affiliate party id
        :return: the sub-graph json
        """
        # extract the requested sub-graph
        ap_graph = self.tp_network.subgraph(self.ap_list[ap_id]).copy()
        # retrieve taxpayer information
        tp_list = self.get_taxpayer_detail(ap_graph)
        # retrieve investor information
        in_list = self.get_investor_detail(ap_graph)

        # # Calculate suspicious value
        # for in_node in in_list:
        #     # 根据每个investor，求她到关联交易的距离和路径数
        #     # node的嫌疑值 = 多条路径上的比例的相乘 的加和
        #     # check if ap_node conducted affiliated party transactions
        #     node_suspect_value = 0
        #     for ap_node in tp_list:  # every taxpayer
        #         if ap_node in self.ap_network:  # if taxpayer conducted related party transaction
        #             # 获取每一个path的invest ratio ,如果是多步就invest ratio相乘
        #             for path in list(nx.all_simple_paths(ap_graph, source=in_node, target=ap_node)):
        #                 weight = 1
        #                 for i in range(len(path)-1):
        #                     e_dict = ap_graph.get_edge_data(path[i], path[i+1])
        #                     weight = weight * e_dict['in_ratio'] if 'in_ratio' in e_dict else 0
        #                 node_suspect_value += weight
        #     ap_graph.add_node(in_node, suspect_value=node_suspect_value)

        # retrieve invoice information
        ap_invoice = self.ap_txn_period.query('buyer_id in @tp_list').query('seller_id in @tp_list')
        # obtain an undirected investment network
        ap_graph_undirected = ap_graph.to_undirected()
        ap_graph_undirected.remove_edges_from(
            [(u, v) for u, v, ap in ap_graph_undirected.edges(data='ap_txn') if ap]
        )
        for u, v, ap_txn in ap_graph.edges(data='ap_txn'):
            if ap_txn:
                # calculate the related strength of each ap_txn
                related_strength = 0
                txn = ap_invoice.query('buyer_id == @u').query('seller_id == @v')['txn_sum']
                # add all simple path of each ap_txn into the graph to be highlighted
                paths = list(nx.all_simple_paths(ap_graph_undirected, source=u, target=v))
                for path in paths:
                    path_strength = 1
                    for i in range(0, len(path)-1):
                        path_strength *= ap_graph_undirected.get_edge_data(path[i], path[i+1])['in_ratio']
                    related_strength += path_strength
                ap_graph.add_edge(
                    u,
                    v,
                    ap_txn_amount=np.sum(txn),
                    ap_txn_count=len(txn),
                    path=paths,
                    related_strength=related_strength
                )

                _profit = self.get_calendar_data_by_tp_id(u, v, '2014-01-01', '2014-12-31')['profit'][-1]
                ap_graph.add_node(u, profit=_profit > 0)
                _profit = self.get_calendar_data_by_tp_id(v, u, '2014-01-01', '2014-12-31')['profit'][-1]
                ap_graph.add_node(v, profit=_profit > 0)

        return nx.node_link_data(ap_graph)

    def get_detail_ap_txn(self, source, target):
        """
        Get the details of affiliated party transactions from source to target
        :param source: seller tp_id
        :param target: buyer tp_id
        :return:
        """
        # find the corresponding ap_graph
        ap_id = self.get_ap_id(source)
        if ap_id == -1:
            return '{}'
        ap_graph = self.tp_network.subgraph(self.ap_list[ap_id])
        ap_graph_undirected = ap_graph.to_undirected(as_view=True)

        # 获取所有path的node list
        paths = list(nx.all_simple_paths(ap_graph_undirected, source=source, target=target))
        node_list = list(set(reduce(lambda x, y: x+y, paths)))

        # 获取对应node list的sub-graph
        detail_ap_txn_graph = ap_graph.subgraph(node_list).copy()
        detail_ap_txn_graph.remove_edges_from(
            [(src, dst) for src, dst, ap_txn in detail_ap_txn_graph.edges(data='ap_txn')
             if (ap_txn & ((src != source) | (dst != target)))])
        self.get_taxpayer_detail(detail_ap_txn_graph)
        self.get_investor_detail(detail_ap_txn_graph)
        return nx.node_link_data(detail_ap_txn_graph)

    def get_calendar_data(self, seller_id, buyer_id, start_time='2014-01-01', end_time='2014-12-31'):
        """
        Return an array first having seller as source, then buyer as source
        :param seller_id: the id of seller
        :param buyer_id: the id of buyer
        :param start_time: the start time of query period
        :param end_time: the end time tof query period
        :return: an array first having seller as source, then buyer as source
        """
        return [
            {'source': self.get_calendar_data_by_tp_id(seller_id, buyer_id, start_time, end_time)},
            {'source': self.get_calendar_data_by_tp_id(buyer_id, seller_id, start_time, end_time)}
        ]

    def get_calendar_data_by_tp_id(self, tp_id, _rtp_id, start_time, end_time):
        """
        Retrieve the all invoices in the period to calculate tp_id cumulative profit, with the portion of ap and rtp.

        The return type can be changed easily in from the options provided in the link:
        https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.to_dict.html
        :param tp_id: the id of source
        :param _rtp_id: the id of target
        :param start_time: the start time of query period
        :param end_time: the end time tof query period
        :return: a dictionary of list {}
        """
        # initialize invoice and DataFrame
        _ap_id = self.get_ap_id(tp_id)
        _ap_list = self.ap_list[_ap_id]
        tp_invoice = self.invoice.query('@start_time <= date <= @end_time')  # filter by time
        tp_invoice = tp_invoice.query('buyer_id == @tp_id or seller_id == @tp_id')  # filter by tp_id
        tp_calendar = pd.DataFrame(index=pd.date_range(start_time, end_time))

        # retrieve total revenue and expense
        tp_revenue = tp_invoice.query('seller_id == @tp_id')
        tp_expense = tp_invoice.query('buyer_id  == @tp_id')
        tp_calendar['revenue'] = tp_revenue[['date', 'txn_sum']].groupby('date').sum()
        tp_calendar['expense'] = tp_expense[['date', 'txn_sum']].groupby('date').sum()

        # retrieve related party revenue and expense
        tp_revenue = tp_revenue.query('buyer_id  in @_ap_list')
        tp_expense = tp_expense.query('seller_id in @_ap_list')
        tp_calendar['ap_revenue'] = tp_revenue[['date', 'txn_sum']].groupby('date').sum()
        tp_calendar['ap_expense'] = tp_expense[['date', 'txn_sum']].groupby('date').sum()

        # retrieve related taxpayer revenue and expense
        tp_revenue = tp_revenue.query('buyer_id  == @_rtp_id')
        tp_expense = tp_expense.query('seller_id == @_rtp_id')
        tp_calendar['rtp_revenue'] = tp_revenue[['date', 'txn_sum']].groupby('date').sum()
        tp_calendar['rtp_expense'] = tp_expense[['date', 'txn_sum']].groupby('date').sum()

        # calculate the profits
        tp_calendar = tp_calendar.fillna(0)
        tp_calendar['profit'] = tp_calendar['revenue'] - tp_calendar['expense']
        tp_calendar['profit'] = tp_calendar.resample('Q')['profit'].cumsum()
        tp_calendar['ap_profit'] = tp_calendar['ap_revenue'] - tp_calendar['ap_expense']
        tp_calendar['rtp_profit'] = tp_calendar['rtp_revenue'] - tp_calendar['rtp_expense']

        # format the DataFrame
        tp_calendar = tp_calendar.astype('int').reset_index().rename(columns={'index': 'date'}).astype({'date': 'str'})
        return tp_calendar.to_dict("list")