# coding=utf-8
import uuid

import hashlib
import json
from time import time
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


if __name__ == '__main__':
    # 服务运行在端口5000上.
    app.run(host='0.0.0.0', port=5000)
