# coding=utf-8
import uuid
from urllib.parse import urlparse

import hashlib
import json
from time import time

import requests
from flask import Flask, request


class Blockchain(object):
    """
    自定义区块链
    """

    def __init__(self):
        """
        构造函数
        """
        # 区块链
        self.chain = []
        # 交易信息
        self.current_transaction = []
        # 节点
        self.nodes = set()

        # 创建创世块
        self.new_block(previous_hash='1', proof=100)

    def new_block(self, proof, previous_hash=None):
        """
        生成新块
        :param proof:<int>  工作量证明
        :param previous_hash:<str>    上一个区块的hash值
        :return: <dict>新块
        """

        # 首次启动进程时,该数据为创世块
        block = {
            'index'        : len(self.chain) + 1,  # 索引
            'timestamp'    : time(),  # 当前时间戳
            'transactions' : self.current_transaction,
            'proof'        : proof,  # 工作量证明
            'previous_hash': previous_hash or self.hash(self.chain[-1]),  # 上一个区块的hash值
        }

        # 重置交易列表
        self.current_transaction = []

        self.chain.append(block)
        return block

    def new_transaction(self, sender, recipient, amount):
        """
        生成新交易信息，信息将加入到下一个待挖的区块中
        :param sender: <str> 发送者地址
        :param recipient: <str> 接受者地址
        :param amount: <int>   金额
        :return: <int> 将持有该事务的块的索引。
        """
        self.current_transaction.append({
            'sender'   : sender,
            'recipient': recipient,
            'amount'   : amount,
        })
        return self.last_block['index'] + 1

    @property
    def last_block(self):
        """
        获取最后一个块
        :return:
        """
        return self.chain[-1]

    @staticmethod
    def hash(block):
        """
        生成块的 SHA-256 hash值
        :param block: <dict> Block
        :return: <str>
        """
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def proof_of_work(self, last_proof):
        """
        简单的工作量证明
        - 查找-个'p'使得hash('pp')以4个0开头
        - p是上一个块的证明,p'是当前的证明
        :param last_proof: <int>
        :return: <int>
        """
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
        """
        验证证明: 是否hash(last_proof,proof)以4个0开头
        :param last_proof:<int> 上一个块的工作量证明
        :param proof:<int>  当前块的工作量证明
        :return:<bool>
        """
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        print(f'当前:{proof} 结果:{guess_hash}')
        return guess_hash[:4] == '0000'

    def register_node(self, address):
        """
        添加新的节点到节点列表
        :param address:<str>节点地址
        :return:None
        """
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def valid_chain(self, chain):
        """
        确定给定的区块链是否有效
        用来检查是否是有效链，遍历每个块验证hash和proof.
        :param chain:<list>一个区块链
        :return:<bool> True if valid, False if not
        """
        last_block = chain[0]
        current_index = 1
        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n-------\n")

            # 检查工作证明是否正确
            if block['previous_hash'] != self.hash(last_block):
                return False

            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        """
        公式算法解决冲突, 使用网络中最长的链
        用来解决冲突，遍历所有的邻居节点，并用上一个方法检查链的有效性， 如果发现有效更长链，就替换掉自己的链
        :return:<bool> True  如果链被取代, 否则为False
        """
        neighbour = self.nodes
        new_chain = None

        # 仅查找比自身更长的链
        max_length = len(self.chain)

        # 从网络中的所有节点获取并验证链
        for node in neighbour:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

            # 检查长度是否较长，链是否有效
            if length > max_length and self.valid_chain(chain):
                max_length = length
                new_chain = chain

        # 如果我们发现一个新的、有效的链比我们的长，就替换我们的链
        if new_chain:
            self.chain = new_chain
            return True

        return False


# 创建一个节点
app = Flask(__name__)

# 为节点创建一个随机的名字
node_identifier = str(uuid.uuid4()).replace('-', '')

# 实例blockchain类
blockchain = Blockchain()


# 创建/mine GET接口
# 告诉服务器去挖掘新的区块
@app.route('/mine', methods=['GET'])
def mine():
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    # 给工作量证明的节点提供奖励.
    # 发送者为 "0" 表明是新挖出的币
    blockchain.new_transaction(
        sender='0',
        recipient=node_identifier,
        amount=1,
    )
    block = blockchain.new_block(proof)
    response = {
        'message'      : "New Block Forged",
        'index'        : block['index'],
        'transactions' : block['transactions'],
        'proof'        : block['proof'],
        'previous_hash': block['previous_hash'],
    }

    return json.dumps(response), 200


# 创建/transactions/new POST接口,可以给接口发送交易数据.
# 基于接口来添加交易就很简单了
# 创建一个交易并添加到区块
@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    # 判断POST提交参数是否符合标准
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return f'参数错误: {k}', 400

    # 创建一个新块
    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])
    response = {'message': f'Transaction will be added to Block {index}'}
    return json.dumps(response), 201


# 创建 /chain 接口, 返回整个区块链。
@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain' : blockchain.chain,
        'length': len(blockchain.chain),
    }
    return json.dumps(response), 200


"""
让我们添加两个路由，一个用来注册节点，一个用来解决冲突。
你可以在不同的机器运行节点，或在一台机机开启不同的网络端口来模拟多节点的网络，
这里在同一台机器开启不同的端口演示，在不同的终端运行一下命令，
就启动了两个节点：http://localhost:5000 和 http://localhost:5001
"""


# 注册节点的路由
@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message'    : 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return json.dumps(response), 201


# 来解决冲突的路由
@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message'  : 'Our chain was replaced',
            'new_chain': blockchain.chain
        }

    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain'  : blockchain.chain
        }

    return json.dumps(response), 201


if __name__ == '__main__':
    # 服务运行在端口5000上.
    app.run(host='0.0.0.0', port=5001)
